from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.core import state


@dataclass
class PipelineRequest:
    ws_id: str
    filename: str


@dataclass
class PipelineJob:
    job_id: str
    status: str


class PipelineWorker:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def enqueue(self, payload: PipelineRequest) -> PipelineJob:
        async with self._lock:
            store = state.StateStore.instance()
            job_id = store.next_job_id()
            # Placeholder for actual pipeline execution
            await asyncio.sleep(0)
            return PipelineJob(job_id=job_id, status="queued")


_worker: PipelineWorker | None = None


def get_pipeline_worker() -> PipelineWorker:
    global _worker
    if _worker is None:
        _worker = PipelineWorker()
    return _worker
