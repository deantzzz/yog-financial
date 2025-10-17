from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.workers.pipeline import PipelineRequest, get_pipeline_worker
from backend.core.workspaces import save_raw_file

router = APIRouter(prefix="/workspaces", tags=["upload"])


@router.post("/{ws_id}/upload")
async def upload_file(ws_id: str, files: list[UploadFile] = File(...)) -> dict:
    """Upload one or more source documents and enqueue them for processing."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file must be provided")

    worker = get_pipeline_worker()
    jobs: list[dict[str, str | None]] = []

    for upload in files:
        try:
            if not upload.filename:
                raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

            safe_name = Path(upload.filename).name
            raw_path = save_raw_file(ws_id, safe_name, upload.file)

            payload = PipelineRequest(
                ws_id=ws_id,
                filename=safe_name,
                file_path=raw_path,
                content_type=upload.content_type,
            )
            job = await worker.enqueue(payload)
            jobs.append({"job_id": job.job_id, "status": job.status, "filename": safe_name})
        finally:
            await upload.close()

    return {"items": jobs}
