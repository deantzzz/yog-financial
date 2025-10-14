"""Application service layer for workspace orchestration."""
from __future__ import annotations

from typing import Iterable

from backend.infrastructure import InMemoryWorkspaceRepository, WorkspaceRepository


class WorkspaceService:
    """Coordinates workspace-related use cases."""

    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------------
    # workspace lifecycle
    # ------------------------------------------------------------------
    def create_workspace(self, month: str) -> str:
        return self._repository.create_workspace(month)

    def get_workspace_overview(self, ws_id: str) -> dict[str, object] | None:
        return self._repository.get_workspace_overview(ws_id)

    # ------------------------------------------------------------------
    # job orchestration
    # ------------------------------------------------------------------
    def next_job_id(self) -> str:
        return self._repository.next_job_id()

    def register_upload(self, ws_id: str, job_id: str, filename: str) -> None:
        self._repository.register_upload(ws_id, job_id, filename)

    def update_job_status(self, ws_id: str, job_id: str, status: str, *, error: str | None = None) -> None:
        self._repository.update_job_status(ws_id, job_id, status, error=error)

    # ------------------------------------------------------------------
    # fact & policy handling
    # ------------------------------------------------------------------
    def list_facts(self, ws_id: str) -> list[dict]:
        return self._repository.list_facts(ws_id)

    def list_policy(self, ws_id: str) -> list[dict]:
        return self._repository.list_policy(ws_id)

    def add_fact(self, ws_id: str, record: dict) -> None:
        self._repository.add_fact(ws_id, record)

    def add_policy(self, ws_id: str, record: dict) -> None:
        self._repository.add_policy(ws_id, record)

    def get_fact_snapshot(self, ws_id: str) -> dict[str, object]:
        return self._repository.get_fact_snapshot(ws_id)

    def get_policy_snapshot(self, ws_id: str) -> dict[str, object]:
        return self._repository.get_policy_snapshot(ws_id)

    def get_fact_records_for_period(self, ws_id: str, period: str) -> list[dict]:
        return [row for row in self.list_facts(ws_id) if row.get("period_month") == period]

    def get_policy_records_for_period(self, ws_id: str, period: str) -> list[dict]:
        return [row for row in self.list_policy(ws_id) if row.get("period_month") == period]

    # ------------------------------------------------------------------
    # results persistence
    # ------------------------------------------------------------------
    def save_results(self, ws_id: str, period: str, rows: Iterable[dict]) -> None:
        self._repository.save_results(ws_id, period, list(rows))

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]:
        return self._repository.list_results(ws_id, period)

    # ------------------------------------------------------------------
    # testing helpers
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._repository.reset()


_repository = InMemoryWorkspaceRepository()
_service = WorkspaceService(_repository)


def get_workspace_service() -> WorkspaceService:
    """Return the singleton workspace service for the process."""

    return _service


def reset_workspace_state() -> None:
    """Reset the in-memory store (used in tests)."""

    _service.reset()
