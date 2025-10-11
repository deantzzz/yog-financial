from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.workers.pipeline import PipelineRequest, get_pipeline_worker
from backend.core.workspaces import save_raw_file

router = APIRouter(prefix="/workspaces", tags=["upload"])


@router.post("/{ws_id}/upload")
async def upload_file(ws_id: str, file: UploadFile = File(...)) -> dict:
    """Upload a source document and enqueue it for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    safe_name = Path(file.filename).name
    raw_path = save_raw_file(ws_id, safe_name, file.file)

    payload = PipelineRequest(ws_id=ws_id, filename=safe_name, file_path=raw_path, content_type=file.content_type)
    worker = get_pipeline_worker()
    job = await worker.enqueue(payload)

    return {"job_id": job.job_id, "status": job.status}
