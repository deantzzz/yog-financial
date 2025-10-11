from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, constr


class FactRecord(BaseModel):
    ws_id: str
    employee_name: str
    employee_name_norm: str
    period_month: constr(pattern=r"^\d{4}-\d{2}$")
    metric_code: Literal[
        "HOUR_STD",
        "HOUR_OT_WD",
        "HOUR_OT_WE",
        "HOUR_TOTAL",
        "HOUR_CONFIRMED",
        "AMOUNT_BASE",
        "AMOUNT_ALLOW",
        "AMOUNT_DEDUCT",
        "AMOUNT_TAX",
        "DAYS_PRESENT",
        "DAYS_ABSENCE",
        "DAYS_LEAVE",
    ]
    metric_value: Decimal
    unit: Literal["hour", "currency", "day"]
    currency: Literal["CNY"] = "CNY"
    tags_json: dict = Field(default_factory=dict)
    metric_label: str | None = None
    source_file: str
    source_sheet: str | None = None
    source_row: int | None = None
    source_col: str | None = None
    source_page: int | None = None
    source_sha256: str
    ingest_job_id: str | None = None
    confidence: Decimal = Decimal("1.0")
    raw_text_hash: str


class PolicySnapshot(BaseModel):
    ws_id: str
    employee_name_norm: str
    period_month: constr(pattern=r"^\d{4}-\d{2}$")
    mode: Literal["SALARIED", "HOURLY"]
    base_amount: Decimal | None = None
    base_rate: Decimal | None = None
    ot_weekday_multiplier: Decimal | None = None
    ot_weekend_multiplier: Decimal | None = None
    ot_weekday_rate: Decimal | None = None
    ot_weekend_rate: Decimal | None = None
    allowances_json: dict = Field(default_factory=dict)
    deductions_json: dict = Field(default_factory=dict)
    tax_json: dict = Field(default_factory=dict)
    social_security_json: dict = Field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None
    raw_snapshot: dict | None = None
    source_file: str | None = None
    source_sheet: str | None = None
    source_row_range: str | None = None
    snapshot_hash: str | None = None


class PayrollResultModel(BaseModel):
    employee_name_norm: str
    period_month: str
    gross_pay: Decimal = Decimal("0")
    net_pay: Decimal = Decimal("0")
    base_pay: Decimal = Decimal("0")
    ot_pay: Decimal = Decimal("0")
    allowances_sum: Decimal = Decimal("0")
    deductions_sum: Decimal = Decimal("0")
    social_security_personal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    snapshot_hash: str | None = None
    rule_version: str = "rules_v1"
    source_files: list[str] = Field(default_factory=list)
