"""Integration with the iFLYTEK OCR for LLM API."""
from __future__ import annotations

import base64
import gzip
import hmac
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .ocr import OCRExtractionResult


class IFlyTekError(RuntimeError):
    """Raised when the remote iFLYTEK service returns an error."""


class IFlyTekOCRClient:
    """Client for the latest iFLYTEK OCR for LLM HTTP API."""

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        *,
        api_base: str = "https://cbm01.cn-huabei-1.xf-yun.com",
        function_id: str = "se75ocrbm",
        request_path: str | None = None,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        parsed = urlparse(api_base)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("api_base must include scheme and host")

        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._host = parsed.netloc

        base_path = (request_path or parsed.path) or f"/v1/private/{function_id}"
        if not base_path.startswith("/"):
            base_path = f"/{base_path}"
        self._request_path = base_path
        self._request_url = f"{parsed.scheme}://{parsed.netloc}{self._request_path}"
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_auth_query(self) -> dict[str, str]:
        """Construct the query parameters required for authenticated calls."""

        date = format_datetime(datetime.now(timezone.utc), usegmt=True)
        request_line = f"POST {self._request_path} HTTP/1.1"
        signature_origin = f"host: {self._host}\ndate: {date}\n{request_line}"

        digest = hmac.new(
            self._api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod="sha256",
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")

        authorization_origin = (
            f'api_key="{self._api_key}",'  # noqa: ISC003 - literal includes quotes
            'algorithm="hmac-sha256",'
            'headers="host date request-line",'
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")

        return {
            "authorization": authorization,
            "host": self._host,
            "date": date,
        }

    @staticmethod
    def _detect_image_encoding(path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        if suffix in {"jpg", "jpeg"}:
            return "jpg"
        if suffix in {"png", "bmp"}:
            return suffix
        return "jpg"

    @staticmethod
    def _serialise_image(path: Path) -> str:
        payload = path.read_bytes()
        return base64.b64encode(payload).decode("ascii")

    def _build_payload(self, path: Path) -> dict[str, Any]:
        encoding = self._detect_image_encoding(path)
        image = self._serialise_image(path)
        return {
            "header": {
                "app_id": self._app_id,
                "status": 0,
            },
            "parameter": {
                "ocr": {
                    "result_option": "normal",
                    "result_format": "json",
                    "output_type": "one_shot",
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json",
                    },
                }
            },
            "payload": {
                "image": {
                    "encoding": encoding,
                    "image": image,
                    "status": 0,
                    "seq": 0,
                }
            },
        }

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None

    @staticmethod
    def _join_unique(parts: list[str]) -> str:
        """Join text fragments while removing duplicates and normalising whitespace."""

        cleaned: list[str] = []
        seen: set[str] = set()
        for part in parts:
            normalised = " ".join(part.split())
            if not normalised:
                continue
            if normalised in seen:
                continue
            seen.add(normalised)
            cleaned.append(normalised)
        return " ".join(cleaned)

    def _collect_tables(self, data: Any) -> list[list[list[str]]]:
        tables: list[list[list[str]]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                node_type = node.get("type") or node.get("element_type")
                if node_type == "table":
                    table = self._normalise_table(node)
                    if table:
                        tables.append(table)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
        return tables

    def _normalise_table(self, table_node: dict[str, Any]) -> list[list[str]]:
        cells = table_node.get("cells") or table_node.get("cell") or table_node.get("body")
        if not isinstance(cells, list):
            return []

        table_map: dict[int, dict[int, str]] = {}
        row_ids: set[int] = set()
        col_ids: set[int] = set()

        for cell in cells:
            if not isinstance(cell, dict):
                continue

            row = self._safe_int(cell.get("row"))
            if row is None:
                row = self._safe_int(cell.get("row_index"))
            if row is None:
                row = self._safe_int(cell.get("start_row"))

            col = self._safe_int(cell.get("col"))
            if col is None:
                col = self._safe_int(cell.get("column"))
            if col is None:
                col = self._safe_int(cell.get("column_index"))
            if col is None:
                col = self._safe_int(cell.get("start_col"))
            if row is None or col is None:
                continue

            text = self._extract_text(cell)
            row_ids.add(row)
            col_ids.add(col)
            table_map.setdefault(row, {})[col] = text

        if not table_map:
            return []

        sorted_rows = sorted(row_ids)
        sorted_cols = sorted(col_ids)

        rows: list[list[str]] = []
        for row_index in sorted_rows:
            row_map = table_map.get(row_index, {})
            row_cells = [row_map.get(col_index, "") for col_index in sorted_cols]
            rows.append(row_cells)
        return rows

    def _extract_text(self, node: Any) -> str:
        if isinstance(node, str):
            return node.strip()
        if isinstance(node, (int, float)):
            return str(node).strip()
        if isinstance(node, dict):
            pieces: list[str] = []
            for key in ("text", "value", "content", "words"):
                if key in node:
                    pieces.append(self._extract_text(node[key]))
            return self._join_unique(pieces)
        if isinstance(node, list):
            parts = [self._extract_text(item) for item in node]
            return self._join_unique(parts)
        return ""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def extract_text(self, path: Path) -> OCRExtractionResult:
        params = self._build_auth_query()
        payload = self._build_payload(path)
        response = self._client.post(self._request_url, params=params, json=payload)
        response.raise_for_status()

        result_payload = response.json()
        header = result_payload.get("header", {})
        code = header.get("code")
        if code not in (0, "0"):
            raise IFlyTekError(str(header.get("message") or code))

        result_data = ((result_payload.get("payload") or {}).get("result")) or {}
        text_field = result_data.get("text") or ""
        encoding = (result_data.get("encoding") or "utf8").lower()
        compress = (result_data.get("compress") or "raw").lower()
        result_format = (result_data.get("format") or "plain").lower()

        decoded_bytes = b""
        if text_field:
            decoded_bytes = base64.b64decode(text_field)
            if compress == "gzip":
                decoded_bytes = gzip.decompress(decoded_bytes)

        decoded_text = decoded_bytes.decode(encoding or "utf-8", errors="replace") if decoded_bytes else ""

        structured: Any | None = None
        if "json" in result_format:
            try:
                structured = json.loads(decoded_text) if decoded_text else None
            except json.JSONDecodeError:  # pragma: no cover - defensive
                structured = None

        tables = self._collect_tables(structured) if structured is not None else []
        primary_table: list[list[str]] = tables[0] if tables else []

        metadata: dict[str, Any] = {
            "provider": "iflytek",
            "tables": primary_table,
            "result_format": result_format,
        }
        if len(tables) > 1:
            metadata["all_tables"] = tables
        if header.get("sid"):
            metadata["sid"] = header["sid"]
        if structured is not None:
            metadata["raw"] = structured
        else:
            metadata["raw_text"] = decoded_text

        return OCRExtractionResult(text=decoded_text, confidence=None, metadata=metadata)

    def close(self) -> None:  # pragma: no cover - best effort cleanup
        if self._owns_client:
            self._client.close()


__all__ = ["IFlyTekOCRClient", "IFlyTekError"]
