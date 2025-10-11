import os
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

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


def test_excel_templates_pipeline(client, tmp_path):
    response = client.post("/api/workspaces", json={"month": "2025-02"})
    assert response.status_code == 200
    ws_id = response.json()["ws_id"]

    # create timesheet aggregate workbook
    agg_wb = Workbook()
    agg_ws = agg_wb.active
    agg_ws.title = "汇总"
    agg_ws.append(["序号", "部门", "姓名", "工作日标准工时", "工作日加班工时", "周末节假日打卡工时", "当月工时（已公式加和）", "确认工时"])
    agg_ws.append([1, "财务部", "李四", 160, 12, 6, 178, 178])
    agg_path = tmp_path / "timesheet.xlsx"
    agg_wb.save(agg_path)

    with agg_path.open("rb") as fp:
        upload = client.post(f"/api/workspaces/{ws_id}/upload", files={"file": ("timesheet.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert upload.status_code == 200

    # create policy workbook
    policy_wb = Workbook()
    policy_ws = policy_wb.active
    policy_ws.title = "薪资"
    policy_ws.append(["姓名", "模式", "基本工资", "工作日加班费率", "周末加班费率", "社保个人比例"])
    policy_ws.append(["李四", "SALARIED", 12000, 50, 80, 0.08])
    policy_path = tmp_path / "policy.xlsx"
    policy_wb.save(policy_path)

    with policy_path.open("rb") as fp:
        upload = client.post(f"/api/workspaces/{ws_id}/upload", files={"file": ("policy.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert upload.status_code == 200

    facts = client.get(f"/api/workspaces/{ws_id}/fact").json()["items"]
    assert any(item["employee_name_norm"] == "李四" and item["metric_code"] == "HOUR_TOTAL" for item in facts)

    policies = client.get(f"/api/workspaces/{ws_id}/policy").json()["items"]
    assert any(item["employee_name_norm"] == "李四" for item in policies)

    calc = client.post(f"/api/workspaces/{ws_id}/calc", json={"period": "2025-02", "selected": ["李四"]})
    assert calc.status_code == 200
    assert calc.json()["items"]


def test_timesheet_with_metadata_header_rows(client, tmp_path):
    response = client.post("/api/workspaces", json={"month": "2025-04"})
    assert response.status_code == 200
    ws_id = response.json()["ws_id"]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "月度工时"
    sheet.append(["填报单位", "卓迈科技", None, None, None, None, None, None])
    sheet.append(["月份", "2025-04", None, None, None, None, None, None])
    sheet.append([None, None, None, None, None, None, None, None])
    sheet.append(
        [
            "序号",
            "部门",
            "姓名",
            "工作日标准工时",
            "工作日加班工时",
            "周末节假日打卡工时",
            "当月工时（已公式加和）",
            "确认工时",
        ]
    )
    sheet.append([1, "生产部", "赵六", 150, 20, 8, 178, 178])
    sheet.append([2, "生产部", "钱七", 160, 18, 6, 184, 184])

    path = tmp_path / "metadata_timesheet.xlsx"
    workbook.save(path)

    with path.open("rb") as fp:
        upload = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={
                "file": (
                    "metadata_timesheet.xlsx",
                    fp,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload.status_code == 200

    facts = client.get(f"/api/workspaces/{ws_id}/fact").json()["items"]
    assert any(item["employee_name_norm"] == "赵六" and item["metric_code"] == "HOUR_TOTAL" for item in facts)
    assert any(item["employee_name_norm"] == "钱七" and item["metric_code"] == "HOUR_STD" for item in facts)


def test_policy_ingestion_case_insensitive_columns(client, tmp_path):
    response = client.post("/api/workspaces", json={"month": "2025-05"})
    assert response.status_code == 200
    ws_id = response.json()["ws_id"]

    policy_rows = [
        {
            "Employee_Name_Norm": "王五",
            "Period_Month": "2025-05",
            "Mode": "salaried",
            "Base_Amount": 12500,
            "Ot_Weekday_Rate": 45,
            "Social_Security_Json": {"employee": 0.08},
        }
    ]
    policy_path = _write_csv(tmp_path, "policy_case.csv", policy_rows)
    with policy_path.open("rb") as fp:
        upload = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={"file": ("policy_case.csv", fp, "text/csv")},
        )
    assert upload.status_code == 200

    response = client.get(f"/api/workspaces/{ws_id}/policy")
    items = response.json()["items"]
    assert items
    policy = next(item for item in items if item["employee_name_norm"] == "王五")

    assert policy["mode"] == "SALARIED"
    assert Decimal(str(policy["base_amount"])) == Decimal("12500")
    assert Decimal(str(policy["ot_weekday_rate"])) == Decimal("45")
    assert policy["ot_weekend_rate"] is None
    assert policy["social_security_json"] == {"employee": 0.08}


def test_excel_heuristic_fallback(client, tmp_path):
    response = client.post("/api/workspaces", json={"month": "2025-03"})
    assert response.status_code == 200
    ws_id = response.json()["ws_id"]

    # workbook with unconventional headers so the template parser emits no rows
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "原始工时"
    sheet.append(["员工姓名", "本月正常工时", "平时加班时长", "周末加班总时长", "核定工时"])
    sheet.append(["王五", 150, 10, 8, 168])
    timesheet_path = tmp_path / "heuristic_timesheet.xlsx"
    workbook.save(timesheet_path)

    with timesheet_path.open("rb") as fp:
        upload = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={"file": ("heuristic_timesheet.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert upload.status_code == 200

    policy_wb = Workbook()
    policy_ws = policy_wb.active
    policy_ws.title = "薪资"
    policy_ws.append(["姓名", "月薪", "平日加班费率", "周末加班费率", "社保个人比例", "餐补津贴"])
    policy_ws.append(["王五", 9000, 45, 70, 0.08, 150])
    policy_path = tmp_path / "heuristic_policy.xlsx"
    policy_wb.save(policy_path)

    with policy_path.open("rb") as fp:
        upload_policy = client.post(
            f"/api/workspaces/{ws_id}/upload",
            files={"file": ("heuristic_policy.xlsx", fp, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert upload_policy.status_code == 200

    facts = client.get(f"/api/workspaces/{ws_id}/fact").json()["items"]
    assert any(item["employee_name_norm"] == "王五" and item["metric_code"] == "HOUR_CONFIRMED" for item in facts)

    policies = client.get(f"/api/workspaces/{ws_id}/policy").json()["items"]
    assert any(item["employee_name_norm"] == "王五" and item.get("base_amount") for item in policies)

    calc = client.post(
        f"/api/workspaces/{ws_id}/calc",
        json={"period": "2025-03", "selected": ["王五"]},
    )
    assert calc.status_code == 200
    assert calc.json()["items"]
