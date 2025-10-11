from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class JobRecord:
    job_id: str
    status: str = "pending"
    filename: str | None = None
    error: str | None = None


@dataclass
class WorkspaceState:
    ws_id: str
    month: str
    jobs: list[JobRecord] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)
    policy: list[dict] = field(default_factory=list)
    results: dict[str, list[dict]] = field(default_factory=dict)


class StateStore:
    _instance: ClassVar["StateStore" | None] = None

    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceState] = {}
        self._job_counter = 0

    @classmethod
    def instance(cls) -> "StateStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Utility used in tests to clear global state."""

        cls._instance = None

    def _ensure_workspace(self, ws_id: str, month: str | None = None) -> WorkspaceState:
        workspace = self._workspaces.get(ws_id)
        if workspace is None:
            workspace = WorkspaceState(ws_id=ws_id, month=month or ws_id)
            self._workspaces[ws_id] = workspace
        elif month and workspace.month != month:
            workspace.month = month
        return workspace

    def create_workspace(self, month: str) -> str:
        ws_id = month
        self._ensure_workspace(ws_id, month)
        return ws_id

    def get_workspace(self, ws_id: str) -> dict | None:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return None
        return {
            "ws_id": ws.ws_id,
            "month": ws.month,
            "jobs": [job.__dict__ for job in ws.jobs],
            "files": [job.__dict__ for job in ws.jobs],
        }

    def register_upload(self, ws_id: str, job_id: str, filename: str) -> None:
        ws = self._ensure_workspace(ws_id)
        ws.jobs.append(JobRecord(job_id=job_id, filename=filename, status="queued"))

    def update_job_status(self, ws_id: str, job_id: str, status: str, error: str | None = None) -> None:
        ws = self._ensure_workspace(ws_id)
        for job in ws.jobs:
            if job.job_id == job_id:
                job.status = status
                job.error = error
                break

    def get_fact_snapshot(self, ws_id: str) -> dict:
        ws = self._ensure_workspace(ws_id)
        return {"items": ws.facts}

    def get_policy_snapshot(self, ws_id: str) -> dict:
        ws = self._ensure_workspace(ws_id)
        return {"items": ws.policy}

    def add_fact(self, ws_id: str, record: dict) -> None:
        ws = self._ensure_workspace(ws_id)
        ws.facts.append(record)

    def add_policy(self, ws_id: str, record: dict) -> None:
        ws = self._ensure_workspace(ws_id)
        ws.policy.append(record)

    def next_job_id(self) -> str:
        self._job_counter += 1
        return f"job-{self._job_counter:05d}"

    def list_facts(self, ws_id: str) -> list[dict]:
        ws = self._workspaces.get(ws_id)
        return list(ws.facts) if ws else []

    def list_policy(self, ws_id: str) -> list[dict]:
        ws = self._workspaces.get(ws_id)
        return list(ws.policy) if ws else []

    def save_results(self, ws_id: str, period: str, rows: list[dict]) -> None:
        ws = self._ensure_workspace(ws_id)
        ws.results[period] = rows

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]:
        ws = self._workspaces.get(ws_id)
        if not ws:
            return []
        if period is None:
            collected: list[dict] = []
            for rows in ws.results.values():
                collected.extend(rows)
            return collected
        return list(ws.results.get(period, []))
