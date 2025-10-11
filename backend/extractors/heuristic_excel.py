"""Heuristic spreadsheet parser used when a workbook cannot be matched to a
known template.

The implementation intentionally favours resilience over precision: it scans
all sheets of the workbook, looks for columns that resemble names and metric
labels, and then emits fact or policy records when the values can be coerced
into decimals.  This mirrors the "模板优先，兜底启发式" 思路 in the 设计文档 by
ensuring that 即使模板识别失败 也尽可能提取可用数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core import name_normalize


FACT_KEYWORDS: dict[str, list[str]] = {
    "HOUR_STD": ["标准工时", "正常工时", "平日工时"],
    "HOUR_OT_WD": ["工作日加班", "平日加班", "平时加班", "普通加班"],
    "HOUR_OT_WE": ["周末加班", "节假日加班", "休息日加班"],
    "HOUR_TOTAL": ["总工时", "当月工时", "工时合计"],
    "HOUR_CONFIRMED": ["确认工时", "核定工时", "确认合计"],
    "AMOUNT_BASE": ["基本工资", "底薪", "月薪", "岗位工资"],
    "AMOUNT_ALLOW": ["津贴", "补贴", "补助"],
    "AMOUNT_DEDUCT": ["扣款", "罚款", "缺勤扣减"],
}

MODE_KEYWORDS = ["模式", "计薪方式", "mode"]
BASE_RATE_KEYWORDS = ["时薪", "hourly", "基准时薪"]
OT_RATE_WD_KEYWORDS = ["工作日加班费率", "平日加班费率", "平日加班时薪"]
OT_RATE_WE_KEYWORDS = ["周末加班费率", "节假日加班费率", "周末加班时薪"]
OT_MULT_WD_KEYWORDS = ["工作日加班倍率", "平日加班倍率"]
OT_MULT_WE_KEYWORDS = ["周末加班倍率", "节假日加班倍率"]
ALLOWANCE_KEYWORDS = ["津贴", "补贴", "补助"]
DEDUCTION_KEYWORDS = ["扣款", "罚款", "缺勤"]
SS_EMPLOYEE_KEYWORDS = ["社保个人", "公积金个人", "个人比例"]
SS_EMPLOYER_KEYWORDS = ["社保公司", "公积金公司", "公司比例"]


@dataclass
class HeuristicParseResult:
    facts: list[dict[str, Any]]
    policies: list[dict[str, Any]]


def _clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: str(col).strip() for col in frame.columns}
    frame = frame.rename(columns=renamed)
    return frame.dropna(how="all")


def _find_column(frame: pd.DataFrame, keywords: list[str]) -> str | None:
    lowered = {col: str(col).lower() for col in frame.columns}
    for column, lower in lowered.items():
        for keyword in keywords:
            if keyword.lower() in lower:
                return column
    return None


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.endswith("%"):
        text = text.strip(" %")
        try:
            return Decimal(text) / Decimal("100")
        except Exception:  # pragma: no cover - defensive
            return None
    try:
        decimal_value = Decimal(text)
    except Exception:  # pragma: no cover - defensive
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _match_metric(column: str) -> str | None:
    lowered = column.lower()
    blocked_tokens = ["费率", "倍率", "比例", "%"]
    if any(token in lowered for token in blocked_tokens):
        return None
    for metric, keywords in FACT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                return metric
    return None


def parse(path: Path, ws_id: str) -> HeuristicParseResult:
    try:
        excel = pd.ExcelFile(path)
    except Exception:  # pragma: no cover - pandas/openpyxl errors
        return HeuristicParseResult(facts=[], policies=[])

    facts: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []

    for sheet_name in excel.sheet_names:
        try:
            frame = excel.parse(sheet_name=sheet_name)
        except Exception:  # pragma: no cover - skip problematic sheets
            continue
        frame = _clean_dataframe(frame)
        if frame.empty:
            continue

        name_column = _find_column(frame, ["姓名", "员工", "name"])
        if not name_column:
            continue

        mode_column = _find_column(frame, MODE_KEYWORDS)
        base_amount_column = _find_column(frame, FACT_KEYWORDS["AMOUNT_BASE"])
        base_rate_column = _find_column(frame, BASE_RATE_KEYWORDS)
        ot_rate_wd_column = _find_column(frame, OT_RATE_WD_KEYWORDS)
        ot_rate_we_column = _find_column(frame, OT_RATE_WE_KEYWORDS)
        ot_mult_wd_column = _find_column(frame, OT_MULT_WD_KEYWORDS)
        ot_mult_we_column = _find_column(frame, OT_MULT_WE_KEYWORDS)
        ss_employee_column = _find_column(frame, SS_EMPLOYEE_KEYWORDS)
        ss_employer_column = _find_column(frame, SS_EMPLOYER_KEYWORDS)

        has_policy_signals = mode_column or base_amount_column or base_rate_column
        has_fact_signals = any(_match_metric(col) for col in frame.columns if col != name_column)

        for index, row in frame.iterrows():
            employee = str(row.get(name_column) or "").strip()
            if not employee or employee in {"合计", "汇总", "总计"}:
                continue
            norm = name_normalize.normalize(employee)

            if has_fact_signals:
                for column in frame.columns:
                    if column == name_column:
                        continue
                    metric = _match_metric(column)
                    if not metric:
                        continue
                    value = _safe_decimal(row.get(column))
                    if value is None:
                        continue
                    facts.append(
                        {
                            "ws_id": ws_id,
                            "employee_name": employee,
                            "employee_name_norm": norm,
                            "period_month": ws_id,
                            "metric_code": metric,
                            "metric_value": value,
                            "unit": "hour" if metric.startswith("HOUR_") else "currency",
                            "metric_label": column,
                            "confidence": Decimal("0.6"),
                            "source_sheet": sheet_name,
                            "source_row": index + 2,  # pandas is zero-based, + header row
                        }
                    )

            if has_policy_signals:
                snapshot: dict[str, Any] = {
                    "ws_id": ws_id,
                    "employee_name_norm": norm,
                    "period_month": ws_id,
                    "mode": str(row.get(mode_column) or "SALARIED").strip().upper()
                    if mode_column
                    else "SALARIED",
                    "source_sheet": sheet_name,
                    "raw_snapshot": {col: row.get(col) for col in frame.columns},
                }
                base_amount = _safe_decimal(row.get(base_amount_column)) if base_amount_column else None
                if base_amount is None:
                    base_amount = _safe_decimal(row.get(base_rate_column)) if base_rate_column else None
                if snapshot["mode"] == "HOURLY":
                    rate_value = _safe_decimal(row.get(base_rate_column)) if base_rate_column else None
                    if rate_value is not None:
                        snapshot["base_rate"] = rate_value
                elif base_amount is not None:
                    snapshot["base_amount"] = base_amount

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
                for column in frame.columns:
                    if column == name_column:
                        continue
                    lowered = column.lower()
                    value = _safe_decimal(row.get(column))
                    if value is None:
                        continue
                    if any(keyword in lowered for keyword in [k.lower() for k in ALLOWANCE_KEYWORDS]):
                        allowances[column] = value
                    if any(keyword in lowered for keyword in [k.lower() for k in DEDUCTION_KEYWORDS]):
                        deductions[column] = value
                if allowances:
                    snapshot["allowances_json"] = {"fixed": allowances}
                if deductions:
                    snapshot["deductions_json"] = {"fixed": deductions}

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

    return HeuristicParseResult(facts=facts, policies=policies)
