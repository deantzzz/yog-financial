"""Domain entities for workspace orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class JobRecord:
    """Represents a background ingestion job bound to a workspace."""

    job_id: str
    status: str = "pending"
    filename: str | None = None
    error: str | None = None


@dataclass(slots=True)
class WorkspaceState:
    """Aggregated state for a single workspace in memory."""

    ws_id: str
    month: str
    jobs: list[JobRecord] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    policy: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
