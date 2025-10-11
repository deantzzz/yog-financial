from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import ast

import pandas as pd

from backend.core import state
from backend.core import hashing, name_normalize
from backend.core.schema import FactRecord, PolicySnapshot
from backend.core.workspaces import copy_into_zone, ensure_workspace_root


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
    def _safe_decimal(value: Any, default: str = "0") -> Decimal:
        try:
            result = Decimal(str(value))
            if not result.is_finite():
                return Decimal(default)
            return result
        except (InvalidOperation, TypeError):
            return Decimal(default)

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
        else:
            # still archive the file under raw, but mark as fact placeholder
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
            period = str(row.get("period_month") or payload.ws_id)
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
        required = {"employee_name_norm", "period_month", "mode"}
        missing = [col for col in required if col not in {c.lower() for c in dataframe.columns}]
        if missing:
            raise ValueError(f"口径数据缺少字段: {', '.join(missing)}")

        sha256 = hashing.sha256_file(payload.file_path)
        store = state.StateStore.instance()
        for row in dataframe.to_dict(orient="records"):
            norm = str(row.get("employee_name_norm") or "")
            if not norm:
                continue

            payload_dict: dict[str, Any] = {
                "ws_id": payload.ws_id,
                "employee_name_norm": norm,
                "period_month": str(row.get("period_month")),
                "mode": str(row.get("mode")),
                "snapshot_hash": row.get("snapshot_hash")
                or hashing.sha256_text(json.dumps(row, sort_keys=True, ensure_ascii=False)),
                "source_file": payload.filename,
                "raw_snapshot": row,
            }

            for key in [
                "base_amount",
                "base_rate",
                "ot_weekday_multiplier",
                "ot_weekend_multiplier",
                "ot_weekday_rate",
                "ot_weekend_rate",
            ]:
                if row.get(key) is not None and row.get(key) != "":
                    payload_dict[key] = self._safe_decimal(row.get(key))

            for json_key in ["allowances_json", "deductions_json", "tax_json", "social_security_json"]:
                value = row.get(json_key)
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
                if row.get(text_key):
                    payload_dict[text_key] = str(row.get(text_key))

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
