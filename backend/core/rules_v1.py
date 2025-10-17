from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

import yaml
from backend.application import get_workspace_service
from backend.core.name_normalize import normalize
from backend.core.schema import FactRecord, PayrollResultModel, PolicySnapshot

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class AggregatedFacts:
    hour_std: Decimal = Decimal("0")
    hour_ot_wd: Decimal = Decimal("0")
    hour_ot_we: Decimal = Decimal("0")
    hour_total: Decimal = Decimal("0")
    hour_confirmed: Decimal = Decimal("0")
    base_amount: Decimal = Decimal("0")
    allowances: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")


class PayrollResult(PayrollResultModel):
    """Typed payroll result used by the calculation API."""


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _load_tax_table() -> dict:
    path = CONFIG_DIR / "tax_tables.cn.yaml"
    if not path.exists():
        return {"default_threshold": 5000, "brackets": []}
    with path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


TAX_TABLE = _load_tax_table()


def _merge_nested_dict(existing: dict | None, incoming: dict | None) -> dict:
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(incoming, dict):
        return dict(existing)

    merged = {key: value for key, value in existing.items()}
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_policy_snapshots(existing: PolicySnapshot | None, incoming: PolicySnapshot) -> PolicySnapshot:
    if existing is None:
        return incoming

    existing_data = existing.model_dump()
    incoming_data = incoming.model_dump()

    numeric_fields = [
        "base_amount",
        "base_rate",
        "ot_weekday_multiplier",
        "ot_weekend_multiplier",
        "ot_weekday_rate",
        "ot_weekend_rate",
    ]
    for field in numeric_fields:
        if existing_data.get(field) is None and incoming_data.get(field) is not None:
            existing_data[field] = incoming_data[field]

    json_fields = [
        "allowances_json",
        "deductions_json",
        "tax_json",
        "social_security_json",
    ]
    for field in json_fields:
        existing_data[field] = _merge_nested_dict(existing_data.get(field), incoming_data.get(field))

    text_fields = ["valid_from", "valid_to", "source_sheet", "source_row_range", "snapshot_hash", "source_file"]
    for field in text_fields:
        if not existing_data.get(field) and incoming_data.get(field):
            existing_data[field] = incoming_data[field]

    if existing_data.get("mode") != incoming_data.get("mode"):
        if existing_data.get("mode") == "SALARIED" and existing_data.get("base_amount") is None:
            existing_data["mode"] = incoming_data.get("mode")
        elif existing_data.get("mode") == "HOURLY" and existing_data.get("base_rate") is None and incoming_data.get("base_amount") is not None:
            existing_data["mode"] = incoming_data.get("mode")

    if not existing_data.get("raw_snapshot") and incoming_data.get("raw_snapshot"):
        existing_data["raw_snapshot"] = incoming_data["raw_snapshot"]

    return PolicySnapshot(**existing_data)


def _aggregate_facts(records: Iterable[FactRecord]) -> AggregatedFacts:
    agg = AggregatedFacts()
    for record in records:
        if record.metric_code == "HOUR_STD":
            agg.hour_std += record.metric_value
        elif record.metric_code == "HOUR_OT_WD":
            agg.hour_ot_wd += record.metric_value
        elif record.metric_code == "HOUR_OT_WE":
            agg.hour_ot_we += record.metric_value
        elif record.metric_code == "HOUR_TOTAL":
            agg.hour_total += record.metric_value
        elif record.metric_code == "HOUR_CONFIRMED":
            agg.hour_confirmed += record.metric_value
        elif record.metric_code == "AMOUNT_BASE":
            agg.base_amount += record.metric_value
        elif record.metric_code == "AMOUNT_ALLOW":
            agg.allowances += record.metric_value
        elif record.metric_code == "AMOUNT_DEDUCT":
            agg.deductions += record.metric_value
    return agg


def _select_hours(agg: AggregatedFacts) -> Decimal:
    return agg.hour_confirmed or agg.hour_total or agg.hour_std


def _apply_tax(gross: Decimal, personal_ss: Decimal) -> Decimal:
    threshold = Decimal(str(TAX_TABLE.get("default_threshold", 5000)))
    taxable = gross - personal_ss - threshold
    if taxable <= 0:
        return Decimal("0")

    remaining = taxable
    tax = Decimal("0")
    for bracket in TAX_TABLE.get("brackets", []):
        limit = bracket.get("limit")
        rate = Decimal(str(bracket.get("rate", 0)))
        bucket = Decimal(str(limit)) if limit is not None else remaining
        if limit is None or remaining <= bucket:
            tax += remaining * rate
            break
        tax += bucket * rate
        remaining -= bucket
        if remaining <= 0:
            break
    return tax


def calculate_period(ws_id: str, period: str, employees: list[str] | None = None) -> list[PayrollResult]:
    service = get_workspace_service()
    fact_rows = [FactRecord(**row) for row in service.get_fact_records_for_period(ws_id, period)]
    policy_rows = [PolicySnapshot(**row) for row in service.get_policy_records_for_period(ws_id, period)]

    selected = {normalize(name) for name in employees} if employees else None

    facts_by_employee: dict[str, list[FactRecord]] = {}
    for record in fact_rows:
        key = normalize(record.employee_name_norm)
        if selected and key not in selected:
            continue
        facts_by_employee.setdefault(key, []).append(record)

    policy_by_employee: dict[str, PolicySnapshot] = {}
    for snapshot in policy_rows:
        key = normalize(snapshot.employee_name_norm)
        policy_by_employee[key] = _merge_policy_snapshots(policy_by_employee.get(key), snapshot)

    results: list[PayrollResult] = []
    for key, records in facts_by_employee.items():
        policy = policy_by_employee.get(key)
        if not policy:
            continue
        agg = _aggregate_facts(records)
        base = Decimal("0")
        ot = Decimal("0")
        hours = _select_hours(agg)
        if policy.mode == "SALARIED":
            base = policy.base_amount or agg.base_amount
            ot += agg.hour_ot_wd * (policy.ot_weekday_rate or Decimal("0"))
            ot += agg.hour_ot_we * (policy.ot_weekend_rate or Decimal("0"))
        else:
            rate = policy.base_rate or Decimal("0")
            base = hours * rate
            mult_wd = policy.ot_weekday_multiplier or Decimal("1")
            mult_we = policy.ot_weekend_multiplier or Decimal("1")
            ot += agg.hour_ot_wd * rate * (mult_wd - Decimal("1"))
            ot += agg.hour_ot_we * rate * (mult_we - Decimal("1"))

        allowances = agg.allowances
        deductions = agg.deductions
        gross = base + ot + allowances
        ss_ratio = Decimal(str(policy.social_security_json.get("employee", 0))) if policy.social_security_json else Decimal("0")
        personal_ss = _quantize(gross * ss_ratio)
        tax_amount = _quantize(_apply_tax(gross, personal_ss))
        net = gross - deductions - personal_ss - tax_amount

        result = PayrollResult(
            employee_name_norm=records[0].employee_name_norm,
            period_month=period,
            gross_pay=_quantize(gross),
            net_pay=_quantize(net),
            base_pay=_quantize(base),
            ot_pay=_quantize(ot),
            allowances_sum=_quantize(allowances),
            deductions_sum=_quantize(deductions),
            social_security_personal=_quantize(personal_ss),
            tax=_quantize(tax_amount),
            snapshot_hash=policy.snapshot_hash,
            source_files=list({record.source_file for record in records}),
        )
        results.append(result)
    return results
