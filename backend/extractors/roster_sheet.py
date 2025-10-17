"""Parser for roster/social security spreadsheets."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from backend.core import name_normalize


@dataclass
class RosterParseResult:
    policies: list[dict[str, Any]]


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
    except Exception:  # pragma: no cover - invalid number
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def parse(path: Path, ws_id: str, sheet_name: str | None = None, period: str | None = None) -> RosterParseResult:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        dataframe = pd.read_csv(path)
    else:
        dataframe = pd.read_excel(path, sheet_name=sheet_name)
    dataframe = _normalise_columns(dataframe)

    name_column = _find_column(dataframe, ["姓名", "员工", "name"])
    if not name_column:
        return RosterParseResult(policies=[])

    personal_ratio_column = _find_column(dataframe, ["个人比例", "个人缴费", "个人%", "个人缴纳"])
    employer_ratio_column = _find_column(dataframe, ["公司比例", "单位比例", "公司缴费", "单位缴纳"])

    base_min_column = _find_column(dataframe, ["最低基数", "下限", "最小基数"])
    base_max_column = _find_column(dataframe, ["最高基数", "上限", "最大基数"])

    policies: list[dict[str, Any]] = []
    for _, row in dataframe.iterrows():
        employee = str(row.get(name_column) or "").strip()
        if not employee:
            continue

        social_security: dict[str, Any] = {}
        if personal_ratio_column:
            value = _safe_decimal(row.get(personal_ratio_column))
            if value is not None:
                social_security["employee"] = value
        if employer_ratio_column:
            value = _safe_decimal(row.get(employer_ratio_column))
            if value is not None:
                social_security["employer"] = value

        base: dict[str, Any] = {}
        if base_min_column:
            value = _safe_decimal(row.get(base_min_column))
            if value is not None:
                base["min"] = value
        if base_max_column:
            value = _safe_decimal(row.get(base_max_column))
            if value is not None:
                base["max"] = value
        if base:
            social_security["base"] = base

        if not social_security:
            continue

        policies.append(
            {
                "ws_id": ws_id,
                "employee_name_norm": name_normalize.normalize(employee),
                "period_month": period or ws_id,
                "mode": "SALARIED",
                "social_security_json": social_security,
                "raw_snapshot": {k: row.get(k) for k in dataframe.columns},
                "source_sheet": sheet_name,
            }
        )

    return RosterParseResult(policies=policies)

