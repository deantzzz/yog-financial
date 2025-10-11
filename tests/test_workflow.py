import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.core import state


@pytest.fixture(autouse=True)
def reset_state():
    state.StateStore.reset()
    yield
    state.StateStore.reset()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACES_ROOT", str(tmp_path))
    from importlib import reload
    from backend.core import workspaces

    reload(workspaces)
    from backend.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _write_csv(tmp_path: Path, filename: str, rows: list[dict]) -> Path:
    df = pd.DataFrame(rows)
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return path


def test_end_to_end_workflow(client, tmp_path):
    # 1. create workspace
    response = client.post("/api/workspaces", json={"month": "2025-01"})
    assert response.status_code == 200
    ws_id = response.json()["ws_id"]

    # 2. upload fact csv
    fact_rows = [
        {
            "employee_name": "张三",
            "period_month": "2025-01",
            "metric_code": "HOUR_TOTAL",
            "metric_value": 160,
            "unit": "hour",
            "confidence": 0.95,
        },
        {
            "employee_name": "张三",
            "period_month": "2025-01",
            "metric_code": "AMOUNT_BASE",
            "metric_value": 10000,
            "unit": "currency",
        },
        {
            "employee_name": "张三",
            "period_month": "2025-01",
            "metric_code": "AMOUNT_ALLOW",
            "metric_value": 500,
            "unit": "currency",
        },
    ]
    fact_path = _write_csv(tmp_path, "facts.csv", fact_rows)
    with fact_path.open("rb") as fp:
        response = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={"file": ("facts.csv", fp, "text/csv")},
        )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Verify job is completed
    response = client.get(f"/api/workspaces/{ws_id}/files")
    data = response.json()
    job = next(item for item in data["files"] if item["job_id"] == job_id)
    assert job["status"] == "completed"

    # 3. upload policy csv
    policy_rows = [
        {
            "employee_name_norm": "张三",
            "period_month": "2025-01",
            "mode": "SALARIED",
            "base_amount": 10000,
            "ot_weekday_rate": 50,
            "ot_weekend_rate": 80,
            "social_security_json": {"employee": 0.1},
        }
    ]
    policy_path = _write_csv(tmp_path, "policy.csv", policy_rows)
    with policy_path.open("rb") as fp:
        response = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={"file": ("policy.csv", fp, "text/csv")},
        )
    assert response.status_code == 200

    # 4. query fact and policy snapshots
    response = client.get(f"/api/workspaces/{ws_id}/fact")
    facts = response.json()["items"]
    assert len(facts) >= 3

    response = client.get(f"/api/workspaces/{ws_id}/policy")
    policies = response.json()["items"]
    assert policies and policies[0]["employee_name_norm"] == "张三"

    # 5. trigger calculation
    response = client.post(
        f"/api/workspaces/{ws_id}/calc",
        json={"period": "2025-01", "selected": ["张三"]},
    )
    assert response.status_code == 200
    assert response.json()["items"]

    # 6. fetch results
    response = client.get(f"/api/workspaces/{ws_id}/results", params={"period": "2025-01"})
    items = response.json()["items"]
    assert items and items[0]["employee_name_norm"] == "张三"
