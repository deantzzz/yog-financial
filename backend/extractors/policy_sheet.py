"""Parser for payroll policy spreadsheets."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core import name_normalize


BASE_COLUMNS = ["基本工资", "底薪", "岗位工资", "薪级", "固定工资"]
RATE_COLUMNS = ["时薪", "hourly", "基准时薪"]
MODE_COLUMNS = ["模式", "计薪方式", "mode"]
PERIOD_COLUMNS = ["月份", "期间", "period"]
ALLOWANCE_COLUMNS = ["津贴", "补贴", "allowance"]
DEDUCTION_COLUMNS = ["扣款", "罚款", "deduction"]
OT_RATE_WD_COLUMNS = ["工作日加班费率", "平日加班费率", "工作日加班时薪"]
OT_RATE_WE_COLUMNS = ["周末加班费率", "节假日加班费率", "周末加班时薪"]
OT_MULT_WD_COLUMNS = ["工作日加班倍率", "平日加班倍率"]
OT_MULT_WE_COLUMNS = ["周末加班倍率", "节假日加班倍率"]
SS_EMP_COLUMNS = ["社保个人比例", "公积金个人比例", "个人缴费比例"]
SS_EMPLOYER_COLUMNS = ["社保公司比例", "公积金公司比例", "公司缴费比例"]


@dataclass
class PolicyParseResult:
    policies: list[dict[str, Any]]


def _normalise_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: str(col).strip() for col in dataframe.columns}
    dataframe = dataframe.rename(columns=renamed)
    return dataframe.dropna(how="all")


def _find_column(dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        for column in dataframe.columns:
            if candidate.lower() in str(column).lower():
                return column
    return None


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().endswith("%"):
        try:
            return Decimal(value.strip(" %")) / Decimal("100")
        except Exception:  # pragma: no cover - invalid percent
            return None
    try:
        decimal_value = Decimal(str(value))
    except Exception:  # pragma: no cover - invalid number
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def parse(
    path: Path,
    ws_id: str,
    sheet_name: str | None = None,
    period: str | None = None,
) -> PolicyParseResult:
    dataframe = pd.read_excel(path, sheet_name=sheet_name)
    dataframe = _normalise_columns(dataframe)

    name_column = _find_column(dataframe, ["姓名", "员工", "employee"])
    if not name_column:
        return PolicyParseResult(policies=[])

    mode_column = _find_column(dataframe, MODE_COLUMNS)
    base_column = _find_column(dataframe, BASE_COLUMNS)
    rate_column = _find_column(dataframe, RATE_COLUMNS)
    period_column = _find_column(dataframe, PERIOD_COLUMNS)
    ot_rate_wd_column = _find_column(dataframe, OT_RATE_WD_COLUMNS)
    ot_rate_we_column = _find_column(dataframe, OT_RATE_WE_COLUMNS)
    ot_mult_wd_column = _find_column(dataframe, OT_MULT_WD_COLUMNS)
    ot_mult_we_column = _find_column(dataframe, OT_MULT_WE_COLUMNS)

    policies: list[dict[str, Any]] = []
    for _, row in dataframe.iterrows():
        employee = str(row.get(name_column) or "").strip()
        if not employee or employee in {"合计", "汇总", "总计"}:
            continue

        snapshot: dict[str, Any] = {
            "ws_id": ws_id,
            "employee_name_norm": name_normalize.normalize(employee),
            "period_month": str(row.get(period_column) or period or ws_id),
            "mode": str(row.get(mode_column) or "SALARIED").strip().upper(),
            "raw_snapshot": {k: row.get(k) for k in dataframe.columns},
            "source_sheet": sheet_name,
        }

        if snapshot["mode"] not in {"SALARIED", "HOURLY"}:
            snapshot["mode"] = "SALARIED"

        base_value = _safe_decimal(row.get(base_column)) if base_column else None
        rate_value = _safe_decimal(row.get(rate_column)) if rate_column else None

        if snapshot["mode"] == "SALARIED" and base_value is not None:
            snapshot["base_amount"] = base_value
        if snapshot["mode"] == "HOURLY" and rate_value is not None:
            snapshot["base_rate"] = rate_value
        if snapshot["mode"] == "SALARIED" and base_value is None and rate_value is not None:
            # 某些表格直接给出时薪，视为 HOURLY
            snapshot["mode"] = "HOURLY"
            snapshot["base_rate"] = rate_value

        if ot_rate_wd_column:
            value = _safe_decimal(row.get(ot_rate_wd_column))
            if value is not None:
                snapshot["ot_weekday_rate"] = value
        if ot_rate_we_column:
            value = _safe_decimal(row.get(ot_rate_we_column))
            if value is not None:
                snapshot["ot_weekend_rate"] = value
        if ot_mult_wd_column:
            value = _safe_decimal(row.get(ot_mult_wd_column))
            if value is not None:
                snapshot["ot_weekday_multiplier"] = value
        if ot_mult_we_column:
            value = _safe_decimal(row.get(ot_mult_we_column))
            if value is not None:
                snapshot["ot_weekend_multiplier"] = value

        allowances: dict[str, Any] = {}
        deductions: dict[str, Any] = {}
        for column in dataframe.columns:
            lowered = str(column).lower()
            value = _safe_decimal(row.get(column))
            if value is None:
                continue
            if any(keyword in lowered for keyword in [key.lower() for key in ALLOWANCE_COLUMNS]):
                allowances[str(column)] = value
            if any(keyword in lowered for keyword in [key.lower() for key in DEDUCTION_COLUMNS]):
                deductions[str(column)] = value

        if allowances:
            snapshot["allowances_json"] = {"fixed": allowances}
        if deductions:
            snapshot["deductions_json"] = {"fixed": deductions}

        ss_employee_column = _find_column(dataframe, SS_EMP_COLUMNS)
        ss_employer_column = _find_column(dataframe, SS_EMPLOYER_COLUMNS)
        social_security: dict[str, Any] = {}
        if ss_employee_column:
            value = _safe_decimal(row.get(ss_employee_column))
            if value is not None:
                social_security["employee"] = value
        if ss_employer_column:
            value = _safe_decimal(row.get(ss_employer_column))
            if value is not None:
                social_security["employer"] = value
        if social_security:
            snapshot["social_security_json"] = social_security

        policies.append(snapshot)

    return PolicyParseResult(policies=policies)

