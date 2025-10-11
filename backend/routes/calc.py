from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.core.rules_v1 import PayrollResult, calculate_period

router = APIRouter(prefix="/workspaces", tags=["calculation"])


@router.post("/{ws_id}/calc")
async def trigger_calculation(ws_id: str, payload: dict) -> dict:
    period = payload.get("period")
    if not period:
        raise HTTPException(status_code=400, detail="period is required")

    employees = payload.get("selected")
    result: list[PayrollResult] = calculate_period(ws_id=ws_id, period=period, employees=employees)
    return {"period": period, "results": [r.model_dump() for r in result]}


@router.get("/{ws_id}/results")
async def get_results(ws_id: str) -> dict:
    return {"ws_id": ws_id, "results": []}
