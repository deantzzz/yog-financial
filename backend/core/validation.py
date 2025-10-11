from __future__ import annotations

from decimal import Decimal

from backend.core.schema import FactRecord, PolicySnapshot


class ValidationError(Exception):
    """Raised when domain validation fails."""


def validate_fact(record: FactRecord) -> None:
    if record.unit == "hour" and (record.metric_value < 0 or record.metric_value > Decimal("744")):
        raise ValidationError("hour value out of bounds")
    if record.unit == "currency" and record.metric_value < Decimal("0"):
        raise ValidationError("currency value cannot be negative")


def validate_policy(policy: PolicySnapshot) -> None:
    if policy.mode == "SALARIED" and policy.base_amount is None:
        raise ValidationError("SALARIED policy must provide base_amount")
    if policy.mode == "HOURLY" and policy.base_rate is None:
        raise ValidationError("HOURLY policy must provide base_rate")
