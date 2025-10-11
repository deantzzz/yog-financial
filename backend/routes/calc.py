from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.core.rules_v1 import PayrollResult, calculate_period
from backend.core import state

router = APIRouter(prefix="/workspaces", tags=["calculation"])


@router.post("/{ws_id}/calc")
async def trigger_calculation(ws_id: str, payload: dict) -> dict:
    period = payload.get("period")
    if not period:
        raise HTTPException(status_code=400, detail="period is required")

    employees = payload.get("selected")
    result: list[PayrollResult] = calculate_period(ws_id=ws_id, period=period, employees=employees)
    rows = [r.model_dump() for r in result]
    state.StateStore.instance().save_results(ws_id, period, rows)
    return {"period": period, "items": rows}


@router.get("/{ws_id}/results")
async def get_results(ws_id: str, period: str | None = Query(default=None)) -> dict:
    rows = state.StateStore.instance().list_results(ws_id, period)
    return {"ws_id": ws_id, "period": period, "items": rows}
