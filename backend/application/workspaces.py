"""Application service layer for workspace orchestration."""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from pydantic import ValidationError

from backend.core.name_normalize import normalize
from backend.core.policy_utils import merge_policy_snapshots
from backend.core.schema import PolicySnapshot
from backend.infrastructure import InMemoryWorkspaceRepository, WorkspaceRepository


class WorkspaceService:
    """Coordinates workspace-related use cases."""

    REQUIREMENTS: dict[str, dict[str, object]] = {
        "timesheet_detail": {
            "id": "timesheet_detail",
            "label": "员工工时明细",  # noqa: RUF001
            "description": "上传个人维度的打卡或工时记录（timesheet_personal 模板）",
            "step": "upload_timesheets",
            "optional": False,
            "schemas": {"timesheet_personal", "heuristic_fact"},
        },
        "timesheet_summary": {
            "id": "timesheet_summary",
            "label": "班组工时汇总",  # noqa: RUF001
            "description": "若有班组/部门汇总表（timesheet_aggregate 模板），可用于核对合计。",
            "step": "upload_timesheets",
            "optional": True,
            "schemas": {"timesheet_aggregate"},
        },
        "employee_roster": {
            "id": "employee_roster",
            "label": "员工花名册",  # noqa: RUF001
            "description": "上传含入离职信息及部门的花名册（roster_sheet 模板）",
            "step": "upload_policy",
            "optional": False,
            "schemas": {"roster_sheet"},
        },
        "policy_rules": {
            "id": "policy_rules",
            "label": "薪酬口径与参数",  # noqa: RUF001
            "description": "上传薪资口径、加班倍率及津贴扣款配置（policy_sheet 模板）",
            "step": "upload_policy",
            "optional": False,
            "schemas": {"policy_sheet", "heuristic_policy"},
        },
    }

    SCHEMA_REQUIREMENT_MAP: dict[str, str] = {
        schema: requirement["id"]
        for requirement in REQUIREMENTS.values()
        for schema in requirement["schemas"]  # type: ignore[misc]
    }

    STEP_DEFINITIONS: list[dict[str, object]] = [
        {
            "id": "workspace_setup",
            "label": "创建工作区",
            "description": "创建计薪月份工作区，所有上传与计算均围绕该月份展开。",
            "type": "system",
        },
        {
            "id": "upload_timesheets",
            "label": "上传工时与计薪基础",
            "description": "按照要求上传工时明细与可选的汇总表，系统会自动解析为事实数据。",
            "requirements": ["timesheet_detail", "timesheet_summary"],
        },
        {
            "id": "upload_policy",
            "label": "上传口径与花名册",
            "description": "上传薪酬口径、社保个税参数及花名册，生成口径快照。",
            "requirements": ["employee_roster", "policy_rules"],
        },
        {
            "id": "review_data",
            "label": "审查解析质量",
            "description": "检查事实层低置信度记录与口径差异，确认无误后方可进入计算。",
            "checkpoint": True,
        },
        {
            "id": "run_payroll",
            "label": "执行计薪并导出",
            "description": "触发工资计算，审阅结果并导出银行及税务报表。",
            "result_step": True,
        },
    ]

    def __init__(self, repository: WorkspaceRepository) -> None:
        self._repository = repository

    # ------------------------------------------------------------------
    # workspace lifecycle
    # ------------------------------------------------------------------
    def create_workspace(self, month: str) -> str:
        return self._repository.create_workspace(month)

    def get_workspace_overview(self, ws_id: str) -> dict[str, object] | None:
        return self._repository.get_workspace_overview(ws_id)

    # ------------------------------------------------------------------
    # job orchestration
    # ------------------------------------------------------------------
    def next_job_id(self) -> str:
        return self._repository.next_job_id()

    def register_upload(self, ws_id: str, job_id: str, filename: str) -> None:
        self._repository.register_upload(ws_id, job_id, filename)

    def update_job_status(self, ws_id: str, job_id: str, status: str, *, error: str | None = None) -> None:
        self._repository.update_job_status(ws_id, job_id, status, error=error)

    def mark_requirement(
        self,
        ws_id: str,
        requirement_id: str,
        *,
        filename: str,
        job_id: str,
        schema: str,
    ) -> None:
        self._repository.mark_requirement(ws_id, requirement_id, filename=filename, job_id=job_id, schema=schema)

    def register_requirement_for_schema(
        self,
        ws_id: str,
        schema: str,
        *,
        filename: str,
        job_id: str,
    ) -> None:
        requirement_id = self.SCHEMA_REQUIREMENT_MAP.get(schema)
        if requirement_id:
            self.mark_requirement(ws_id, requirement_id, filename=filename, job_id=job_id, schema=schema)

    # ------------------------------------------------------------------
    # fact & policy handling
    # ------------------------------------------------------------------
    def list_facts(self, ws_id: str) -> list[dict]:
        return self._repository.list_facts(ws_id)

    def list_policy(self, ws_id: str) -> list[dict]:
        rows = self._repository.list_policy(ws_id)

        aggregated: dict[tuple[str, str], PolicySnapshot] = {}
        passthrough: list[dict] = []
        for row in rows:
            try:
                snapshot = PolicySnapshot(**row)
            except ValidationError:
                passthrough.append(row)
                continue

            key = (normalize(snapshot.employee_name_norm), str(snapshot.period_month or ""))
            aggregated[key] = merge_policy_snapshots(aggregated.get(key), snapshot)

        merged_rows = [snapshot.model_dump() for snapshot in aggregated.values()]
        merged_rows.extend(passthrough)
        return merged_rows

    def add_fact(self, ws_id: str, record: dict) -> None:
        self._repository.add_fact(ws_id, record)

    def add_policy(self, ws_id: str, record: dict) -> None:
        self._repository.add_policy(ws_id, record)

    def add_document_record(self, ws_id: str, record: dict) -> None:
        self._repository.add_document(ws_id, record)

    def list_documents(self, ws_id: str) -> list[dict]:
        return self._repository.list_documents(ws_id)

    def get_fact_snapshot(self, ws_id: str) -> dict[str, object]:
        return self._repository.get_fact_snapshot(ws_id)

    def get_policy_snapshot(self, ws_id: str) -> dict[str, object]:
        return {"items": self.list_policy(ws_id)}

    def get_fact_records_for_period(self, ws_id: str, period: str) -> list[dict]:
        return [row for row in self.list_facts(ws_id) if row.get("period_month") == period]

    def get_policy_records_for_period(self, ws_id: str, period: str) -> list[dict]:
        return [row for row in self.list_policy(ws_id) if row.get("period_month") == period]

    # ------------------------------------------------------------------
    # results persistence
    # ------------------------------------------------------------------
    def save_results(self, ws_id: str, period: str, rows: Iterable[dict]) -> None:
        self._repository.save_results(ws_id, period, list(rows))

    def list_results(self, ws_id: str, period: str | None = None) -> list[dict]:
        return self._repository.list_results(ws_id, period)

    def list_workspaces(self) -> list[dict[str, object]]:
        return self._repository.list_workspaces()

    def update_checkpoint(self, ws_id: str, step_id: str, status: str) -> None:
        self._repository.update_checkpoint(ws_id, step_id, status)

    def get_workspace_progress(self, ws_id: str) -> dict[str, object] | None:
        overview = self.get_workspace_overview(ws_id)
        if not overview:
            return None

        requirements_state = self._repository.get_requirements(ws_id)
        checkpoints = overview.get("checkpoints") or {}
        jobs = overview.get("jobs") or []
        job_counter = Counter(str(job.get("status") or "unknown") for job in jobs)
        facts = self.list_facts(ws_id)
        policies = self.list_policy(ws_id)
        results = self.list_results(ws_id, None)

        def _to_float(value: object) -> float | None:
            try:
                result = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            if result != result:  # NaN
                return None
            return result

        low_confidence = sum(1 for item in facts if (confidence := _to_float(item.get("confidence"))) is not None and confidence < 0.8)
        result_periods = sorted({str(item.get("period_month")) for item in results if item.get("period_month")})

        facts_count = len(facts)
        policies_count = len(policies)
        results_count = len(results)

        requirement_outputs: list[dict[str, object]] = []
        for requirement_id, definition in self.REQUIREMENTS.items():
            state = requirements_state.get(requirement_id, {})
            status = str(state.get("status") or "pending")
            auto_inferred = False
            if requirement_id == "timesheet_detail" and status != "completed" and facts_count > 0:
                status = "completed"
                auto_inferred = True
            entry = {
                "id": requirement_id,
                "label": definition["label"],
                "description": definition["description"],
                "optional": bool(definition.get("optional", False)),
                "status": status,
                "filename": state.get("filename"),
                "job_id": state.get("job_id"),
                "schema": state.get("schema"),
                "updated_at": state.get("updated_at"),
                "step_id": definition["step"],
                "auto_inferred": auto_inferred,
            }
            requirement_outputs.append(entry)

        steps: list[dict[str, object]] = []
        completed_steps = 0
        next_step: str | None = None
        prerequisites_completed = True
        pending_jobs = sum(job_counter.get(state, 0) for state in ("queued", "pending", "processing"))
        failed_jobs = sum(job_counter.get(state, 0) for state in ("failed", "error"))

        for step in self.STEP_DEFINITIONS:
            step_id = str(step["id"])
            requirements = [
                {key: value for key, value in item.items() if key != "step_id"}
                for item in requirement_outputs
                if item["step_id"] == step_id
            ]
            meta: dict[str, object] = {}

            if step_id == "workspace_setup":
                status = "completed"
                meta = {"month": overview.get("month")}
            elif step_id in {"upload_timesheets", "upload_policy"}:
                satisfied = [req for req in requirements if req["status"] == "completed"]
                non_optional = [req for req in requirements if not req["optional"]]
                required_completed = all(req["status"] == "completed" for req in non_optional)
                any_progress = bool(satisfied)
                if not prerequisites_completed:
                    status = "blocked"
                elif required_completed:
                    status = "completed"
                elif any_progress:
                    status = "in_progress"
                else:
                    status = "pending"
                meta = {
                    "requirements": requirements,
                    "fact_rows": facts_count if step_id == "upload_timesheets" else None,
                    "policy_rows": policies_count if step_id == "upload_policy" else None,
                }
                meta = {k: v for k, v in meta.items() if v is not None}
            elif step_id == "review_data":
                if not prerequisites_completed:
                    status = "blocked"
                else:
                    checkpoint_status = str(checkpoints.get(step_id, "pending"))
                    status = "completed" if checkpoint_status == "completed" else "pending"
                    meta = {
                        "checkpoint_status": checkpoint_status,
                        "facts_count": facts_count,
                        "policies_count": policies_count,
                        "low_confidence": low_confidence,
                        "pending_jobs": pending_jobs,
                        "failed_jobs": failed_jobs,
                    }
            elif step_id == "run_payroll":
                if not prerequisites_completed:
                    status = "blocked"
                else:
                    status = "completed" if results_count > 0 else "pending"
                    meta = {
                        "results_count": results_count,
                        "available_periods": result_periods,
                    }
            else:
                status = "pending" if prerequisites_completed else "blocked"

            steps.append(
                {
                    "id": step_id,
                    "label": step["label"],
                    "description": step["description"],
                    "status": status,
                    "requirements": requirements,
                    "meta": meta,
                }
            )

            if status == "completed":
                completed_steps += 1
            elif prerequisites_completed and next_step is None and status != "blocked":
                next_step = step_id

            prerequisites_completed = prerequisites_completed and status == "completed"

        overall = round(completed_steps / len(self.STEP_DEFINITIONS), 4)

        summary = {
            "jobs": {
                "total": sum(job_counter.values()),
                "by_status": dict(job_counter),
                "pending": pending_jobs,
                "failed": failed_jobs,
            },
            "facts": {"count": facts_count, "low_confidence": low_confidence},
            "policy": {"count": policies_count},
            "results": {"count": results_count, "periods": result_periods},
        }

        return {
            "ws_id": overview.get("ws_id") or ws_id,
            "month": overview.get("month") or ws_id,
            "overall": overall,
            "steps": steps,
            "next_step": next_step,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # testing helpers
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._repository.reset()


_repository = InMemoryWorkspaceRepository()
_service = WorkspaceService(_repository)


def get_workspace_service() -> WorkspaceService:
    """Return the singleton workspace service for the process."""

    return _service


def reset_workspace_state() -> None:
    """Reset the in-memory store (used in tests)."""

    _service.reset()
