"""Parser for the 月度工时汇总确认表."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core import name_normalize


METRIC_COLUMNS = {
    "HOUR_STD": ["工作日标准工时", "标准工时"],
    "HOUR_OT_WD": ["工作日加班工时", "平日加班"],
    "HOUR_OT_WE": ["周末节假日打卡工时", "周末加班", "节假日加班"],
    "HOUR_TOTAL": ["当月工时", "当月工时（已公式加和）", "总工时"],
    "HOUR_CONFIRMED": ["确认工时"],
}


@dataclass
class AggregateParseResult:
    facts: list[dict[str, Any]]


def _normalise_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: str(col).strip() for col in dataframe.columns}
    dataframe = dataframe.rename(columns=renamed)
    return dataframe.dropna(how="all")


def _find_column(dataframe: pd.DataFrame, keywords: list[str]) -> str | None:
    for keyword in keywords:
        for column in dataframe.columns:
            if keyword in str(column):
                return column
    return None


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        decimal_value = Decimal(str(value))
    except Exception:  # pragma: no cover - non numeric value
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def parse(
    path: Path,
    ws_id: str,
    sheet_name: str | None = None,
    period: str | None = None,
) -> AggregateParseResult:
    period_month = period or ws_id
    dataframe = pd.read_excel(path, sheet_name=sheet_name)
    dataframe = _normalise_columns(dataframe)

    name_column = _find_column(dataframe, ["姓名", "员工", "name"])
    if not name_column:
        return AggregateParseResult(facts=[])

    metric_columns: dict[str, str] = {}
    for metric, keywords in METRIC_COLUMNS.items():
        column = _find_column(dataframe, keywords)
        if column:
            metric_columns[metric] = column

    facts: list[dict[str, Any]] = []
    for idx, row in dataframe.iterrows():
        employee = str(row.get(name_column) or "").strip()
        if not employee or employee in {"合计", "汇总", "总计"}:
            continue

        for metric_code, column in metric_columns.items():
            value = _safe_decimal(row.get(column))
            if value is None:
                continue
            unit = "hour" if metric_code.startswith("HOUR_") else "currency"
            facts.append(
                {
                    "employee_name": employee,
                    "employee_name_norm": name_normalize.normalize(employee),
                    "period_month": period_month,
                    "metric_code": metric_code,
                    "metric_value": value,
                    "unit": unit,
                    "metric_label": column,
                    "confidence": Decimal("0.9"),
                    "source_sheet": sheet_name,
                    "source_row": int(idx) + 2,
                }
            )

    return AggregateParseResult(facts=facts)

