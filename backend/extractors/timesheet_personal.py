"""Parser for the 个人工时表."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from backend.core import name_normalize


@dataclass
class PersonalParseResult:
    facts: list[dict[str, Any]]


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        decimal_value = Decimal(str(value))
    except Exception:  # pragma: no cover - defensive
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _find_metadata(ws, keyword: str) -> str | None:
    for row in ws.iter_rows(min_row=1, max_row=15, max_col=10):
        for cell in row:
            value = cell.value
            if value and keyword in str(value):
                neighbour = ws.cell(row=cell.row, column=cell.column + 1)
                if neighbour.value is None:
                    continue
                return str(neighbour.value).strip()
    return None


def _find_header_row(ws) -> int | None:
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        labels = [str(cell.value).strip() if cell.value is not None else "" for cell in row]
        if "日期" in labels and ("总工时" in labels or "工时" in labels):
            return row[0].row
    return None


def parse(path: Path, ws_id: str, sheet_name: str | None = None, period: str | None = None) -> PersonalParseResult:
    workbook = load_workbook(path, data_only=True)
    worksheet = workbook[sheet_name] if sheet_name and sheet_name in workbook.sheetnames else workbook.active

    employee_name = _find_metadata(worksheet, "姓名") or ""
    month = _find_metadata(worksheet, "月份") or period or ws_id
    header_row = _find_header_row(worksheet)
    if not header_row:
        return PersonalParseResult(facts=[])

    headers = [str(cell.value).strip() if cell.value else "" for cell in worksheet[header_row]]
    indices = {header: idx for idx, header in enumerate(headers)}

    totals = {
        "HOUR_TOTAL": Decimal("0"),
        "HOUR_STD": Decimal("0"),
        "HOUR_OT_WD": Decimal("0"),
        "HOUR_OT_WE": Decimal("0"),
    }

    for row in worksheet.iter_rows(min_row=header_row + 1, values_only=True):
        if all(cell is None for cell in row):
            continue
        if row[0] in {"合计", "总计"}:
            continue

        if "总工时" in indices:
            value = _safe_decimal(row[indices["总工时"]])
            if value:
                totals["HOUR_TOTAL"] += value
        if "标准工时" in indices:
            value = _safe_decimal(row[indices["标准工时"]])
            if value:
                totals["HOUR_STD"] += value
        if "加班工时" in indices:
            value = _safe_decimal(row[indices["加班工时"]])
            if value:
                totals["HOUR_OT_WD"] += value
        if "周末节假日打卡工时" in indices:
            value = _safe_decimal(row[indices["周末节假日打卡工时"]])
            if value:
                totals["HOUR_OT_WE"] += value

    facts: list[dict[str, Any]] = []
    if employee_name:
        for metric, total in totals.items():
            if total == 0:
                continue
            facts.append(
                {
                    "employee_name": employee_name,
                    "employee_name_norm": name_normalize.normalize(employee_name),
                    "period_month": month,
                    "metric_code": metric,
                    "metric_value": total,
                    "unit": "hour",
                    "metric_label": "个人工时汇总",
                    "confidence": Decimal("0.8"),
                    "source_sheet": worksheet.title,
                }
            )

    return PersonalParseResult(facts=facts)

