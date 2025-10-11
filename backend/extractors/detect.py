"""Basic template detection helpers for Excel uploads.

The detector inspects the column names (and a few sample rows) of the
workbook in order to categorise the spreadsheet into one of the known
schemas.  The goal is not to be bullet proof but to cover the canonical
templates that the MVP supports:

* 个人工时模板 → ``timesheet_personal``
* 月度汇总确认表 → ``timesheet_aggregate``
* 工资计算表（口径） → ``policy_sheet``
* 员工名册/社保 → ``roster_sheet``

If no schema can be identified the caller should fall back to the generic
placeholder handling in the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


KEYWORDS_TIMESHEET_PERSONAL = ["日期", "标准工时", "加班工时", "总工时"]
KEYWORDS_TIMESHEET_AGG = [
    "工作日标准工时",
    "工作日加班工时",
    "周末",
    "确认工时",
    "当月工时",
]
KEYWORDS_POLICY = ["基本工资", "底薪", "加班", "津贴", "扣款", "社保", "公积金", "个税"]
KEYWORDS_ROSTER = ["身份证", "社保基数", "个人比例", "入职", "离职"]
POLICY_CORE = ["模式", "mode", "基本", "底薪", "时薪"]


@dataclass
class DetectedTemplate:
    schema: str
    sheet: str | None = None


def _normalise(text: str | int | float | None) -> str:
    if text is None:
        return ""
    return str(text).strip()


def _column_tokens(columns: Iterable[str]) -> list[str]:
    return [col.strip().lower() for col in columns if isinstance(col, str)]


def _contains_keywords(columns: Iterable[str], keywords: Iterable[str]) -> bool:
    lowered = _column_tokens(columns)
    return any(keyword.lower() in col for col in lowered for keyword in keywords)


def _detect_from_frame(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None

    # ``metric_code`` is our canonical fact import schema
    lowered = _column_tokens(frame.columns)
    if "metric_code" in lowered:
        return "fact_table"
    if "mode" in lowered and "employee_name_norm" in lowered:
        return "policy_table"

    if (
        _contains_keywords(frame.columns, KEYWORDS_POLICY)
        and any(core.lower() in col for col in _column_tokens(frame.columns) for core in POLICY_CORE)
    ):
        return "policy_sheet"
    if _contains_keywords(frame.columns, KEYWORDS_TIMESHEET_AGG):
        return "timesheet_aggregate"
    if _contains_keywords(frame.columns, KEYWORDS_TIMESHEET_PERSONAL):
        return "timesheet_personal"
    if _contains_keywords(frame.columns, KEYWORDS_ROSTER):
        return "roster_sheet"
    return None


def detect_excel(path: Path) -> DetectedTemplate:
    """Attempt to classify an Excel workbook."""

    try:
        excel = pd.ExcelFile(path)
    except Exception:  # pragma: no cover - pandas/openpyxl level errors
        return DetectedTemplate(schema="unknown", sheet=None)

    for sheet_name in excel.sheet_names:
        try:
            frame = excel.parse(sheet_name=sheet_name, nrows=20)
        except Exception:  # pragma: no cover - skip problematic sheets
            continue
        schema = _detect_from_frame(frame)
        if schema:
            return DetectedTemplate(schema=schema, sheet=sheet_name)
    return DetectedTemplate(schema="unknown", sheet=None)


def detect(path: Path) -> DetectedTemplate:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return detect_excel(path)
    if suffix == ".csv":
        try:
            frame = pd.read_csv(path, nrows=5)
        except Exception:  # pragma: no cover - invalid csv
            return DetectedTemplate(schema="unknown", sheet=None)
        schema = _detect_from_frame(frame)
        return DetectedTemplate(schema=schema or "unknown", sheet=None)
    if suffix == ".json":
        return DetectedTemplate(schema="json_payload", sheet=None)
    return DetectedTemplate(schema="unknown", sheet=None)

