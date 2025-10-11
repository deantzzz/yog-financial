from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import ast

try:  # pragma: no cover - import-time fallback
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - executed in minimal envs
    from backend.utils import simple_dataframe as pd

from backend.core import state
from backend.core import hashing, name_normalize
from backend.core.csvio import write_records_to_csv
from backend.core.schema import FactRecord, PolicySnapshot
from backend.core.workspaces import copy_into_zone, ensure_workspace_root
from backend.extractors import detect
from backend.extractors import (
    heuristic_excel,
    policy_sheet as policy_parser,
    roster_sheet as roster_parser,
    timesheet_aggregate as aggregate_parser,
    timesheet_personal as personal_parser,
)


@dataclass
class PipelineRequest:
    ws_id: str
    filename: str
    file_path: Path
    content_type: str | None = None


@dataclass
class PipelineJob:
    job_id: str
    status: str


class PipelineWorker:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @staticmethod
    def _json_sanitise(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, list):
            return [PipelineWorker._json_sanitise(item) for item in value]
        if isinstance(value, dict):
            return {key: PipelineWorker._json_sanitise(val) for key, val in value.items()}
        return value

    @staticmethod
    def _safe_decimal(value: Any, default: str = "0") -> Decimal:
        try:
            result = Decimal(str(value))
            if not result.is_finite():
                return Decimal(default)
            return result
        except (InvalidOperation, TypeError):
            return Decimal(default)

    @staticmethod
    def _normalise_period_month(value: Any, fallback: str) -> str:
        fallback = str(fallback or "1970-01")
        fallback_match = re.fullmatch(r"(\d{4})-(\d{2})", fallback)
        fallback_year = fallback_match.group(1) if fallback_match else "1970"
        fallback_month = fallback_match.group(2) if fallback_match else "01"

        if value is None:
            return f"{fallback_year}-{fallback_month}"

        raw = str(value).strip()
        if not raw:
            return f"{fallback_year}-{fallback_month}"

        if re.fullmatch(r"\d{4}-\d{2}", raw):
            return raw

        year = fallback_year
        month_number: int | None = None

        digits = re.findall(r"\d+", raw)
        for number in digits:
            if len(number) == 4 and number.isdigit() and number.startswith(("19", "20")):
                year = number
            elif month_number is None:
                try:
                    candidate = int(number)
                except ValueError:
                    continue
                if 1 <= candidate <= 12:
                    month_number = candidate

        lowered = raw.lower()
        month_keywords: dict[int, tuple[str, ...]] = {
            1: ("jan", "january", "一月", "壹月", "正月"),
            2: ("feb", "february", "二月", "贰月"),
            3: ("mar", "march", "三月", "叁月"),
            4: ("apr", "april", "四月", "肆月"),
            5: ("may", "五月", "伍月"),
            6: ("jun", "june", "六月", "陆月"),
            7: ("jul", "july", "七月", "柒月"),
            8: ("aug", "august", "八月", "捌月"),
            9: ("sep", "sept", "september", "九月", "玖月"),
            10: ("oct", "october", "十月", "拾月"),
            11: ("nov", "november", "十一月"),
            12: ("dec", "december", "十二月", "腊月"),
        }

        if month_number is None:
            for number, keywords in month_keywords.items():
                if any(keyword in lowered for keyword in keywords):
                    month_number = number
                    break

        if month_number is None:
            month_number = int(fallback_month)

        return f"{year}-{month_number:02d}"

    async def enqueue(self, payload: PipelineRequest) -> PipelineJob:
        async with self._lock:
            store = state.StateStore.instance()
            job_id = store.next_job_id()
            store.register_upload(payload.ws_id, job_id, payload.filename)
            store.update_job_status(payload.ws_id, job_id, "processing")
            try:
                await asyncio.to_thread(self._process_file, payload, job_id)
            except Exception as exc:  # pragma: no cover - defensive branch
                store.update_job_status(payload.ws_id, job_id, "failed", error=str(exc))
                raise
            else:
                store.update_job_status(payload.ws_id, job_id, "completed")
            return PipelineJob(job_id=job_id, status="completed")

    def _process_file(self, payload: PipelineRequest, job_id: str) -> None:
        ensure_workspace_root(payload.ws_id)
        suffix = payload.file_path.suffix.lower()
        if suffix == ".csv":
            copy_into_zone(payload.ws_id, payload.file_path, "csv")
            self._ingest_csv(payload, job_id)
        elif suffix == ".json":
            copy_into_zone(payload.ws_id, payload.file_path, "json")
            self._ingest_json(payload, job_id)
        elif suffix in {".xlsx", ".xls", ".xlsm"}:
            template = detect.detect(payload.file_path)
            sheet_name = template.sheet
            handled_fact = False
            handled_policy = False
            fact_signatures: set[tuple[str | None, str | None, str | None]] = set()

            if template.schema == "timesheet_personal":
                result = personal_parser.parse(
                    payload.file_path,
                    ws_id=payload.ws_id,
                    sheet_name=sheet_name,
                )
                if result.facts:
                    self._ingest_fact_records(payload, job_id, result.facts, template.schema)
                    handled_fact = True
                    fact_signatures.update(
                        (
                            item.get("employee_name_norm"),
                            item.get("metric_code"),
                            item.get("metric_label"),
                        )
                        for item in result.facts
                    )
            elif template.schema == "timesheet_aggregate":
                result = aggregate_parser.parse(
                    payload.file_path,
                    ws_id=payload.ws_id,
                    sheet_name=sheet_name,
                )
                if result.facts:
                    self._ingest_fact_records(payload, job_id, result.facts, template.schema)
                    handled_fact = True
                    fact_signatures.update(
                        (
                            item.get("employee_name_norm"),
                            item.get("metric_code"),
                            item.get("metric_label"),
                        )
                        for item in result.facts
                    )
            elif template.schema == "policy_sheet":
                result = policy_parser.parse(
                    payload.file_path,
                    ws_id=payload.ws_id,
                    sheet_name=sheet_name,
                )
                if result.policies:
                    self._ingest_policy_records(payload, job_id, result.policies, template.schema)
                    handled_policy = True
            elif template.schema == "roster_sheet":
                result = roster_parser.parse(
                    payload.file_path,
                    ws_id=payload.ws_id,
                    sheet_name=sheet_name,
                )
                if result.policies:
                    self._ingest_policy_records(payload, job_id, result.policies, template.schema)
                    handled_policy = True

            heuristic = heuristic_excel.parse(payload.file_path, ws_id=payload.ws_id)
            heuristic_facts = [
                item
                for item in heuristic.facts
                if (
                    item.get("employee_name_norm"),
                    item.get("metric_code"),
                    item.get("metric_label"),
                )
                not in fact_signatures
            ]

            if heuristic_facts:
                self._ingest_fact_records(payload, job_id, heuristic_facts, "heuristic")
                handled_fact = True

            if not handled_policy and heuristic.policies:
                self._ingest_policy_records(payload, job_id, heuristic.policies, "heuristic")
                handled_policy = True

            if not handled_fact and not handled_policy:
                self._record_unparsed(payload, job_id)
        else:
            self._record_unparsed(payload, job_id)

    def _ingest_csv(self, payload: PipelineRequest, job_id: str) -> None:
        dataframe = pd.read_csv(payload.file_path)
        columns = {col.lower(): col for col in dataframe.columns}
        if "metric_code" in columns:
            self._ingest_fact_rows(payload, job_id, dataframe)
        elif "mode" in columns:
            self._ingest_policy_rows(payload, job_id, dataframe)
        else:
            raise ValueError("CSV 模板未识别，请包含 metric_code 或 mode 列")

    def _ingest_json(self, payload: PipelineRequest, job_id: str) -> None:
        with payload.file_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if "records" in data:
            rows = pd.DataFrame(data["records"])
            self._ingest_fact_rows(payload, job_id, rows)
        if "policy" in data:
            rows = data["policy"]
            dataframe = pd.DataFrame(rows if isinstance(rows, list) else [rows])
            self._ingest_policy_rows(payload, job_id, dataframe)

    def _ingest_fact_records(
        self,
        payload: PipelineRequest,
        job_id: str,
        records: list[dict[str, Any]],
        schema: str,
    ) -> None:
        if not records:
            self._record_unparsed(payload, job_id)
            return
        dataframe = pd.DataFrame(records)
        self._ingest_fact_rows(payload, job_id, dataframe)
        root = ensure_workspace_root(payload.ws_id)
        target = root / "csv" / f"{Path(payload.filename).stem}_{schema}.csv"
        write_records_to_csv(target, records)

    def _ingest_policy_records(
        self,
        payload: PipelineRequest,
        job_id: str,
        records: list[dict[str, Any]],
        schema: str,
    ) -> None:
        if not records:
            self._record_unparsed(payload, job_id)
            return
        dataframe = pd.DataFrame(records)
        self._ingest_policy_rows(payload, job_id, dataframe)
        root = ensure_workspace_root(payload.ws_id)
        target = root / "policy" / f"{Path(payload.filename).stem}_{schema}.csv"
        write_records_to_csv(target, records)

    def _record_unparsed(self, payload: PipelineRequest, job_id: str) -> None:
        record = {
            "ws_id": payload.ws_id,
            "employee_name": "未分类文件",
            "employee_name_norm": "uncategorized",
            "period_month": payload.ws_id,
            "metric_code": "AMOUNT_ALLOW",
            "metric_value": Decimal("0"),
            "unit": "currency",
            "metric_label": "unparsed",
            "source_file": payload.filename,
            "source_sha256": hashing.sha256_file(payload.file_path),
            "ingest_job_id": job_id,
            "confidence": Decimal("0"),
            "raw_text_hash": hashing.sha256_text(payload.filename),
        }
        state.StateStore.instance().add_fact(payload.ws_id, record)

    def _ingest_fact_rows(self, payload: PipelineRequest, job_id: str, dataframe: pd.DataFrame) -> None:
        required = {"employee_name", "period_month", "metric_code", "metric_value"}
        missing = [col for col in required if col not in {c.lower() for c in dataframe.columns}]
        if missing:
            raise ValueError(f"事实数据缺少字段: {', '.join(missing)}")

        sha256 = hashing.sha256_file(payload.file_path)
        store = state.StateStore.instance()
        for row in dataframe.to_dict(orient="records"):
            employee_name = str(row.get("employee_name") or "")
            if not employee_name:
                continue
            norm = row.get("employee_name_norm") or name_normalize.normalize(employee_name)
            period = self._normalise_period_month(row.get("period_month"), payload.ws_id)
            metric_code = str(row.get("metric_code") or "")
            metric_raw = row.get("metric_value", "0")
            metric_value = self._safe_decimal(metric_raw or "0")
            unit = row.get("unit") or ("hour" if metric_code.startswith("HOUR_") else "currency")
            tags = row.get("tags_json")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    try:
                        tags = ast.literal_eval(tags)
                    except (ValueError, SyntaxError):
                        tags = {}
            if not isinstance(tags, dict):
                tags = {}

            fact = FactRecord(
                ws_id=payload.ws_id,
                employee_name=employee_name,
                employee_name_norm=str(norm),
                period_month=period,
                metric_code=metric_code,  # type: ignore[arg-type]
                metric_value=metric_value,
                unit=unit,  # type: ignore[arg-type]
                metric_label=str(row.get("metric_label") or metric_code),
                source_file=payload.filename,
                source_sheet=row.get("source_sheet"),
                source_row=int(row.get("source_row")) if row.get("source_row") is not None else None,
                source_col=row.get("source_col"),
                source_page=int(row.get("source_page")) if row.get("source_page") is not None else None,
                source_sha256=sha256,
                ingest_job_id=job_id,
                confidence=self._safe_decimal(row.get("confidence", "1"), default="1"),
                raw_text_hash=hashing.sha256_text(
                    "|".join(
                        [
                            payload.ws_id,
                            employee_name,
                            period,
                            metric_code,
                            str(row.get("metric_value")),
                        ]
                    )
                ),
                tags_json=tags,
            )
            store.add_fact(payload.ws_id, fact.model_dump())

    def _ingest_policy_rows(self, payload: PipelineRequest, job_id: str, dataframe: pd.DataFrame) -> None:
        normalised_columns = {
            str(column).strip().lower(): column for column in dataframe.columns
        }

        required = {"employee_name_norm", "period_month", "mode"}
        missing = [col for col in required if col not in normalised_columns]
        if missing:
            raise ValueError(f"口径数据缺少字段: {', '.join(missing)}")

        sha256 = hashing.sha256_file(payload.file_path)
        store = state.StateStore.instance()
        rows = dataframe.to_dict(orient="records")

        def get_value(row: dict[str, Any], key: str) -> Any:
            column = normalised_columns.get(key)
            if column is None:
                return None
            return row.get(column)

        for row in rows:
            norm = str(get_value(row, "employee_name_norm") or "")
            if not norm:
                continue

            sanitized_row = {
                key: self._json_sanitise(value) for key, value in row.items()
            }

            payload_dict: dict[str, Any] = {
                "ws_id": payload.ws_id,
                "employee_name_norm": norm,
                "period_month": self._normalise_period_month(
                    get_value(row, "period_month"), payload.ws_id
                ),
                "mode": str(get_value(row, "mode") or "SALARIED").upper(),
                "snapshot_hash": get_value(row, "snapshot_hash")
                or hashing.sha256_text(
                    json.dumps(sanitized_row, sort_keys=True, ensure_ascii=False)
                ),
                "source_file": payload.filename,
                "raw_snapshot": sanitized_row,
            }

            for key in [
                "base_amount",
                "base_rate",
                "ot_weekday_multiplier",
                "ot_weekend_multiplier",
                "ot_weekday_rate",
                "ot_weekend_rate",
            ]:
                value = get_value(row, key)
                if value is not None and value != "":
                    payload_dict[key] = self._safe_decimal(value)

            for json_key in ["allowances_json", "deductions_json", "tax_json", "social_security_json"]:
                value = get_value(row, json_key)
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        try:
                            value = ast.literal_eval(value)
                        except (ValueError, SyntaxError):
                            value = {}
                if value is None:
                    value = {}
                payload_dict[json_key] = value

            for text_key in ["valid_from", "valid_to", "source_sheet", "source_row_range"]:
                text_value = get_value(row, text_key)
                if text_value:
                    payload_dict[text_key] = str(text_value)

            payload_dict["source_sha256"] = sha256
            payload_dict["ingest_job_id"] = job_id

            snapshot = PolicySnapshot(**payload_dict)
            store.add_policy(payload.ws_id, snapshot.model_dump())


_worker: PipelineWorker | None = None


def get_pipeline_worker() -> PipelineWorker:
    global _worker
    if _worker is None:
        _worker = PipelineWorker()
    return _worker
