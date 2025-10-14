from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

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
