"""Infrastructure layer for workspace persistence."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
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

    def add_document(self, ws_id: str, record: dict) -> None: ...

    def list_documents(self, ws_id: str) -> list[dict]: ...

    def get_policy_snapshot(self, ws_id: str) -> dict[str, object]: ...

    def get_fact_snapshot(self, ws_id: str) -> dict[str, object]: ...

    def save_results(self, ws_id: str, period: str, rows: list[dict]) -> None: ...

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]: ...

    def next_job_id(self) -> str: ...

    def list_workspaces(self) -> list[dict[str, object]]: ...

    def mark_requirement(
        self,
        ws_id: str,
        requirement_id: str,
        *,
        filename: str,
        job_id: str,
        schema: str,
    ) -> None: ...

    def get_requirements(self, ws_id: str) -> dict[str, dict[str, object]]: ...

    def update_checkpoint(self, ws_id: str, step_id: str, status: str) -> None: ...

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
        documents = list(workspace.documents)
        return {
            "ws_id": workspace.ws_id,
            "month": workspace.month,
            "jobs": jobs,
            "files": jobs,
            "documents": documents,
            "requirements": dict(workspace.requirements),
            "checkpoints": dict(workspace.checkpoints),
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

    def add_document(self, ws_id: str, record: dict) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.documents.append(record)

    def list_documents(self, ws_id: str) -> list[dict]:
        workspace = self._workspaces.get(ws_id)
        return list(workspace.documents) if workspace else []

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

    def list_workspaces(self) -> list[dict[str, object]]:
        summaries: list[dict[str, object]] = []
        for workspace in self._workspaces.values():
            summaries.append(
                {
                    "ws_id": workspace.ws_id,
                    "month": workspace.month,
                    "jobs": len(workspace.jobs),
                    "facts": len(workspace.facts),
                    "policy": len(workspace.policy),
                    "results": sum(len(rows) for rows in workspace.results.values()),
                }
            )
        summaries.sort(key=lambda item: item["month"], reverse=True)
        return summaries

    def mark_requirement(
        self,
        ws_id: str,
        requirement_id: str,
        *,
        filename: str,
        job_id: str,
        schema: str,
    ) -> None:
        workspace = self._ensure_workspace(ws_id)
        workspace.requirements[requirement_id] = {
            "status": "completed",
            "filename": filename,
            "job_id": job_id,
            "schema": schema,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_requirements(self, ws_id: str) -> dict[str, dict[str, object]]:
        workspace = self._ensure_workspace(ws_id)
        return dict(workspace.requirements)

    def update_checkpoint(self, ws_id: str, step_id: str, status: str) -> None:
        workspace = self._ensure_workspace(ws_id)
        if status:
            workspace.checkpoints[step_id] = status
        elif step_id in workspace.checkpoints:
            del workspace.checkpoints[step_id]

    def reset(self) -> None:
        self._workspaces.clear()
        self._job_counter = 0
