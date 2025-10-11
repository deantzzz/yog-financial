from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.core import state

router = APIRouter(prefix="/workspaces", tags=["workspace"])


@router.post("")
async def create_workspace(payload: dict) -> dict:
    month = payload.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="month is required")
    ws_id = state.StateStore.instance().create_workspace(month)
    return {"ws_id": ws_id}


@router.get("/{ws_id}/files")
async def list_workspace_files(ws_id: str) -> dict:
    data = state.StateStore.instance().get_workspace(ws_id)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return data


@router.get("/{ws_id}/fact")
async def get_fact_records(ws_id: str) -> dict:
    return state.StateStore.instance().get_fact_snapshot(ws_id)


@router.get("/{ws_id}/policy")
async def get_policy_snapshot(ws_id: str) -> dict:
    return state.StateStore.instance().get_policy_snapshot(ws_id)
