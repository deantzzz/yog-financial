"""Integration with the iFLYTEK OCR HTTP API."""
from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

from .ocr import OCRClient, OCRExtractionResult


class IFlyTekError(RuntimeError):
    """Raised when the remote iFLYTEK service returns an error."""


class IFlyTekOCRClient:
    """Minimal OCR client that talks to the iFLYTEK WebAPI service."""

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        *,
        host: str = "https://webapi.xfyun.cn/v1/service/v1/ocr/recognize_table",
        timeout: float = 15.0,
    ) -> None:
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._host = host.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_headers(self) -> dict[str, str]:
        cur_time = str(int(time.time()))
        params = base64.b64encode(json.dumps({"engine_type": "table"}).encode("utf-8")).decode("ascii")
        checksum_raw = self._api_key + cur_time + params
        checksum = hashlib.md5(checksum_raw.encode("utf-8")).hexdigest()
        return {
            "X-Appid": self._app_id,
            "X-CurTime": cur_time,
            "X-Param": params,
            "X-CheckSum": checksum,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        }

    @staticmethod
    def _serialise_image(path: Path) -> str:
        payload = path.read_bytes()
        return base64.b64encode(payload).decode("ascii")

    @staticmethod
    def _extract_table(data: dict[str, Any]) -> list[list[str]]:
        """Convert iFLYTEK table body cells into a dense matrix."""

        body = data.get("body") or data.get("table") or data.get("cells")
        if not isinstance(body, list):
            # fall back to text payload as a single row table
            text = data.get("text") or data.get("content") or ""
            lines = [line.strip() for line in str(text).splitlines() if line.strip()]
            return [line.split() for line in lines] if lines else []

        table_map: dict[int, dict[int, str]] = {}
        max_col = 0
        for cell in body:
            if not isinstance(cell, dict):
                continue
            row = int(cell.get("row", cell.get("row_index", 0)))
            column = int(cell.get("column", cell.get("col_index", 0)))
            text = cell.get("content") or cell.get("text") or cell.get("words") or ""
            table_map.setdefault(row, {})[column] = str(text)
            max_col = max(max_col, column)

        rows: list[list[str]] = []
        for row_index in sorted(table_map.keys()):
            row_cells: list[str] = []
            row_map = table_map[row_index]
            for column in range(max_col + 1):
                row_cells.append(row_map.get(column, ""))
            rows.append(row_cells)
        return rows

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def extract_text(self, path: Path) -> OCRExtractionResult:
        image = self._serialise_image(path)
        headers = self._build_headers()
        response = self._client.post(self._host, headers=headers, data={"image": image})
        response.raise_for_status()

        payload = response.json()
        if payload.get("code") not in {"0", 0}:
            raise IFlyTekError(str(payload.get("desc") or payload.get("message") or payload))

        data = payload.get("data") or {}
        text = data.get("text") or data.get("content") or ""
        table_rows = self._extract_table(data)
        confidence_raw = data.get("confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else None
        except (TypeError, ValueError):  # pragma: no cover - defensive
            confidence = None

        metadata = {
            "provider": "iflytek",
            "raw": data,
            "tables": table_rows,
        }
        return OCRExtractionResult(text=str(text), confidence=confidence, metadata=metadata)

    def close(self) -> None:  # pragma: no cover - best effort cleanup
        self._client.close()


__all__ = ["IFlyTekOCRClient", "IFlyTekError"]
