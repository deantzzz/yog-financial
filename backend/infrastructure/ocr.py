"""Lightweight OCR integration hooks.

The project currently does not connect to a commercial OCR provider.  This
module defines a minimal abstraction so that the pipeline can request text
extraction while tests run against a deterministic no-op implementation.  A
future integration only needs to provide a compatible client and call
``configure_ocr_client`` during application start-up.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class OCRClient(Protocol):
    """Contract for OCR integrations."""

    def extract_text(self, path: Path) -> "OCRExtractionResult":
        """Extract text content from the provided file."""


@dataclass(slots=True)
class OCRExtractionResult:
    """Container returned by :class:`OCRClient` implementations."""

    text: str
    confidence: float | None = None
    metadata: dict[str, object] | None = None


class NoOpOCRClient:
    """Fallback OCR client used when no provider is configured."""

    def extract_text(self, path: Path) -> OCRExtractionResult:  # pragma: no cover - trivial
        return OCRExtractionResult(
            text="",
            confidence=None,
            metadata={
                "provider": "noop",
                "reason": "OCR integration not configured",
                "filename": path.name,
            },
        )


_client: OCRClient = NoOpOCRClient()


def configure_ocr_client(client: OCRClient) -> None:
    """Install the OCR client used by the ingestion pipeline."""

    global _client
    _client = client


def get_ocr_client() -> OCRClient:
    """Return the currently configured OCR client."""

    return _client
