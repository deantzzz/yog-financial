"""File type detection helpers for structured and unstructured uploads.

The detector inspects spreadsheet content in order to categorise the
workbook into one of the known schemas.  The goal is not to be bullet proof
but to cover the canonical templates that the MVP supports:

* 个人工时模板 → ``timesheet_personal``
* 月度汇总确认表 → ``timesheet_aggregate``
* 工资计算表（口径） → ``policy_sheet``
* 员工名册/社保 → ``roster_sheet``

For non-tabular uploads the detector falls back to extension based
classification so that callers can route files to the OCR pipeline.
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


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}
TEXT_SUFFIXES = {".txt", ".md", ".rtf"}


@dataclass
class DetectedTemplate:
    schema: str
    sheet: str | None = None
    requires_ocr: bool = False


def _normalise(text: str | int | float | None) -> str:
    if text is None:
        return ""
    return str(text).strip()


def _column_tokens(columns: Iterable[str]) -> list[str]:
    return [col.strip().lower() for col in columns if isinstance(col, str)]


def _contains_keywords(columns: Iterable[str], keywords: Iterable[str]) -> bool:
    lowered = _column_tokens(columns)
    return any(keyword.lower() in col for col in lowered for keyword in keywords)


def _detect_from_tokens(tokens: Iterable[str]) -> str | None:
    lowered = [token.strip().lower() for token in tokens if isinstance(token, str) and token.strip()]
    if not lowered:
        return None

    if "metric_code" in lowered:
        return "fact_table"
    if "mode" in lowered and "employee_name_norm" in lowered:
        return "policy_table"

    if any(keyword.lower() in token for token in lowered for keyword in KEYWORDS_POLICY) and any(
        core.lower() in token for token in lowered for core in POLICY_CORE
    ):
        return "policy_sheet"

    def _has_any(options: Iterable[str]) -> bool:
        return any(option.lower() in token for token in lowered for option in options)

    roster_hits = sum(
        1 for keyword in KEYWORDS_ROSTER for token in lowered if keyword.lower() in token
    )
    personal_ratio = _has_any(["个人比例", "个人缴费", "个人%", "个人缴纳"])
    employer_ratio = _has_any(["公司比例", "单位比例", "公司缴费", "单位缴纳"])
    base_hint = _has_any(["基数", "下限", "上限"])
    lifecycle_hint = _has_any(["入职", "离职"])
    id_hint = _has_any(["身份证"])

    if roster_hits >= 2 or (
        personal_ratio and (employer_ratio or base_hint or lifecycle_hint)
    ) or (id_hint and (personal_ratio or employer_ratio or base_hint or lifecycle_hint)):
        return "roster_sheet"
    if any(keyword.lower() in token for token in lowered for keyword in KEYWORDS_TIMESHEET_AGG):
        return "timesheet_aggregate"
    if any(keyword.lower() in token for token in lowered for keyword in KEYWORDS_TIMESHEET_PERSONAL):
        return "timesheet_personal"
    return None


def _detect_from_frame(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None

    schema = _detect_from_tokens(frame.columns)
    if schema:
        return schema

    # When the real header is not the first row pandas will treat the data
    # rows as the header.  Iterate over the sample rows and attempt detection
    # using each row as if it were the header.
    for _, row in frame.iterrows():
        schema = _detect_from_tokens(row.tolist())
        if schema:
            return schema
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
    if suffix in IMAGE_SUFFIXES:
        return DetectedTemplate(schema="image_document", sheet=None, requires_ocr=True)
    if suffix in DOCUMENT_SUFFIXES:
        return DetectedTemplate(schema="unstructured_document", sheet=None, requires_ocr=True)
    if suffix in TEXT_SUFFIXES:
        return DetectedTemplate(schema="text_document", sheet=None, requires_ocr=False)
    return DetectedTemplate(schema="unknown", sheet=None)

