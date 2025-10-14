"""Infrastructure layer for workspace persistence."""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from backend.domain import JobRecord, WorkspaceState


class WorkspaceRepository(Protocol):
    """Persistence contract for workspace state."""

    def create_workspace(self, month: str) -> str: ...

    def get_workspace_overview(self, ws_id: str) -> dict[str, object] | None: ...

    def register_upload(self, ws_id: str, job_id: str, filename: str) -> None: ...

    def update_job_status(self, ws_id: str, job_id: str, status: str, *, error: str | None = None) -> None: ...

    def add_fact(self, ws_id: str, record: dict) -> None: ...

    def list_facts(self, ws_id: str) -> list[dict]: ...

    def add_policy(self, ws_id: str, record: dict) -> None: ...

    def list_policy(self, ws_id: str) -> list[dict]: ...

    def get_policy_snapshot(self, ws_id: str) -> dict[str, object]: ...

    def get_fact_snapshot(self, ws_id: str) -> dict[str, object]: ...

    def save_results(self, ws_id: str, period: str, rows: list[dict]) -> None: ...

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]: ...

    def next_job_id(self) -> str: ...

    def reset(self) -> None: ...


class InMemoryWorkspaceRepository:
    """Simple in-memory repository for fast iteration and tests."""

    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceState] = {}
        self._job_counter = 0

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _ensure_workspace(self, ws_id: str, month: str | None = None) -> WorkspaceState:
        workspace = self._workspaces.get(ws_id)
        if workspace is None:
            workspace = WorkspaceState(ws_id=ws_id, month=month or ws_id)
            self._workspaces[ws_id] = workspace
        elif month and workspace.month != month:
            workspace.month = month
        return workspace

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------
    def create_workspace(self, month: str) -> str:
        ws_id = month
        self._ensure_workspace(ws_id, month)
        return ws_id

    def get_workspace_overview(self, ws_id: str) -> dict[str, object] | None:
        workspace = self._workspaces.get(ws_id)
        if workspace is None:
            return None
        jobs = [asdict(job) for job in workspace.jobs]
        return {
            "ws_id": workspace.ws_id,
            "month": workspace.month,
            "jobs": jobs,
            "files": jobs,
        }

    def register_upload(self, ws_id: str, job_id: str, filename: str) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.jobs.append(JobRecord(job_id=job_id, filename=filename, status="queued"))

    def update_job_status(self, ws_id: str, job_id: str, status: str, *, error: str | None = None) -> None:
        workspace = self._ensure_workspace(ws_id)
        for job in workspace.jobs:
            if job.job_id == job_id:
                job.status = status
                job.error = error
                break

    def add_fact(self, ws_id: str, record: dict) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.facts.append(record)

    def list_facts(self, ws_id: str) -> list[dict]:
        workspace = self._workspaces.get(ws_id)
        return list(workspace.facts) if workspace else []

    def add_policy(self, ws_id: str, record: dict) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.policy.append(record)

    def list_policy(self, ws_id: str) -> list[dict]:
        workspace = self._workspaces.get(ws_id)
        return list(workspace.policy) if workspace else []

    def get_policy_snapshot(self, ws_id: str) -> dict[str, object]:
        workspace = self._ensure_workspace(ws_id)
        return {"items": list(workspace.policy)}

    def get_fact_snapshot(self, ws_id: str) -> dict[str, object]:
        workspace = self._ensure_workspace(ws_id)
        return {"items": list(workspace.facts)}

    def save_results(self, ws_id: str, period: str, rows: list[dict]) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.results[period] = rows

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]:
        workspace = self._workspaces.get(ws_id)
        if workspace is None:
            return []
        if period is None:
            aggregated: list[dict] = []
            for rows in workspace.results.values():
                aggregated.extend(rows)
            return aggregated
        return list(workspace.results.get(period, []))

    def next_job_id(self) -> str:
        self._job_counter += 1
        return f"job-{self._job_counter:05d}"

    def reset(self) -> None:
        self._workspaces.clear()
        self._job_counter = 0
