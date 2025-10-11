from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.core import state
from backend.workers.pipeline import PipelineRequest, get_pipeline_worker

router = APIRouter(prefix="/workspaces", tags=["upload"])


@router.post("/{ws_id}/upload")
async def upload_file(ws_id: str, file: UploadFile = File(...)) -> dict:
    """Upload a source document and enqueue it for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    payload = PipelineRequest(ws_id=ws_id, filename=file.filename)
    worker = get_pipeline_worker()
    job = await worker.enqueue(payload)
    state.StateStore.instance().register_upload(ws_id=ws_id, job_id=job.job_id, filename=file.filename)

    return {"job_id": job.job_id, "status": job.status}
