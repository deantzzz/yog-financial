from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.application import get_workspace_service
from backend.core.workspaces import ensure_workspace_root

router = APIRouter(prefix="/workspaces", tags=["workspace"])


@router.get("")
async def list_workspaces() -> dict:
    service = get_workspace_service()
    items = service.list_workspaces()
    return {"items": items}


@router.post("")
async def create_workspace(payload: dict) -> dict:
    month = payload.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month is required")
    service = get_workspace_service()
    ws_id = service.create_workspace(month)
    ensure_workspace_root(ws_id)
    return {"ws_id": ws_id}


@router.get("/{ws_id}/files")
async def list_workspace_files(ws_id: str) -> dict:
    service = get_workspace_service()
    data = service.get_workspace_overview(ws_id)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return data


@router.get("/{ws_id}/progress")
async def get_workspace_progress(ws_id: str) -> dict:
    service = get_workspace_service()
    progress = service.get_workspace_progress(ws_id)
    if not progress:
        raise HTTPException(status_code=404, detail="workspace not found")
    return progress


@router.post("/{ws_id}/progress/checkpoints")
async def update_workspace_checkpoint(ws_id: str, payload: dict) -> dict:
    step = payload.get("step")
    status = str(payload.get("status") or "completed")
    if not step:
        raise HTTPException(status_code=400, detail="step is required")
    if status not in {"pending", "completed"}:
        raise HTTPException(status_code=400, detail="status must be pending or completed")
    service = get_workspace_service()
    if not service.get_workspace_overview(ws_id):
        raise HTTPException(status_code=404, detail="workspace not found")
    service.update_checkpoint(ws_id, step, status)
    progress = service.get_workspace_progress(ws_id)
    return {"step": step, "status": status, "progress": progress}


@router.get("/{ws_id}/fact")
async def get_fact_records(
    ws_id: str,
    employee_name: str | None = Query(default=None),
    metric_code: str | None = Query(default=None),
) -> dict:
    service = get_workspace_service()
    records = service.list_facts(ws_id)
    if employee_name:
        keyword = employee_name.strip().lower()
        records = [item for item in records if keyword in item.get("employee_name_norm", "").lower()]
    if metric_code:
        records = [item for item in records if item.get("metric_code") == metric_code]
    return {"items": records}


@router.get("/{ws_id}/policy")
async def get_policy_snapshot(ws_id: str) -> dict:
    service = get_workspace_service()
    return service.get_policy_snapshot(ws_id)


def _serialise_document(ws_id: str, record: dict[str, Any]) -> dict[str, Any]:
    document = dict(record)
    document_id = str(document.get("document_id") or document.get("ingest_job_id"))
    document["document_id"] = document_id
    document.setdefault("review_status", "pending")
    document["image_url"] = f"/api/workspaces/{ws_id}/documents/{document_id}/image"
    return document


def _normalise_table(value: Any) -> list[list[str]]:
    table: list[list[str]] = []
    if isinstance(value, list):
        for row in value:
            if isinstance(row, list):
                table.append([str(cell) if cell is not None else "" for cell in row])
    return table


def _get_document_record(ws_id: str, document_id: str) -> dict[str, Any]:
    service = get_workspace_service()
    documents = service.list_documents(ws_id)
    for record in documents:
        if str(record.get("document_id")) == document_id:
            return record
    raise HTTPException(status_code=404, detail="document not found")


@router.get("/{ws_id}/documents")
async def list_workspace_documents(ws_id: str) -> dict:
    service = get_workspace_service()
    if not service.get_workspace_overview(ws_id):
        raise HTTPException(status_code=404, detail="workspace not found")
    documents = service.list_documents(ws_id)
    return {"items": [_serialise_document(ws_id, record) for record in documents]}


@router.get("/{ws_id}/documents/{document_id}")
async def get_workspace_document(ws_id: str, document_id: str) -> dict:
    record = _get_document_record(ws_id, document_id)
    return _serialise_document(ws_id, record)


@router.get("/{ws_id}/documents/{document_id}/image")
async def get_workspace_document_image(ws_id: str, document_id: str) -> FileResponse:
    record = _get_document_record(ws_id, document_id)
    rel_path = record.get("document_path")
    if not rel_path:
        raise HTTPException(status_code=404, detail="document image not available")
    root = ensure_workspace_root(ws_id)
    candidate = (root / Path(rel_path)).resolve()
    if not str(candidate).startswith(str(root.resolve())):
        raise HTTPException(status_code=400, detail="invalid document path")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="document image not found")
    return FileResponse(candidate)


@router.put("/{ws_id}/documents/{document_id}")
async def update_workspace_document(ws_id: str, document_id: str, payload: dict[str, Any]) -> dict:
    service = get_workspace_service()
    if not service.get_workspace_overview(ws_id):
        raise HTTPException(status_code=404, detail="workspace not found")

    updates: dict[str, Any] = {}
    if "ocr_text" in payload:
        updates["ocr_text"] = str(payload["ocr_text"] or "")
    if "ocr_table" in payload:
        updates["ocr_table"] = _normalise_table(payload["ocr_table"])
    if "review_status" in payload:
        updates["review_status"] = str(payload["review_status"] or "")
    if "ocr_metadata" in payload and isinstance(payload["ocr_metadata"], dict):
        updates["ocr_metadata"] = payload["ocr_metadata"]

    if not updates:
        raise HTTPException(status_code=400, detail="no valid updates provided")

    try:
        updated = service.update_document_record(ws_id, document_id, updates)
    except KeyError as exc:  # pragma: no cover - defensive, should translate to 404
        raise HTTPException(status_code=404, detail="document not found") from exc
    return _serialise_document(ws_id, updated)
