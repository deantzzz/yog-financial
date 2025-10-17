"""Helpers for combining payroll policy snapshots from multiple sources."""

from __future__ import annotations

from backend.core.schema import PolicySnapshot


def _merge_nested_dict(existing: dict | None, incoming: dict | None) -> dict:
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(incoming, dict):
        return dict(existing)

    merged = {key: value for key, value in existing.items()}
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_policy_snapshots(existing: PolicySnapshot | None, incoming: PolicySnapshot) -> PolicySnapshot:
    """Combine two policy snapshots, preferring populated fields from ``incoming``."""

    if existing is None:
        return incoming

    existing_data = existing.model_dump()
    incoming_data = incoming.model_dump()

    numeric_fields = [
        "base_amount",
        "base_rate",
        "ot_weekday_multiplier",
        "ot_weekend_multiplier",
        "ot_weekday_rate",
        "ot_weekend_rate",
    ]
    for field in numeric_fields:
        if existing_data.get(field) is None and incoming_data.get(field) is not None:
            existing_data[field] = incoming_data[field]

    json_fields = [
        "allowances_json",
        "deductions_json",
        "tax_json",
        "social_security_json",
    ]
    for field in json_fields:
        existing_data[field] = _merge_nested_dict(existing_data.get(field), incoming_data.get(field))

    text_fields = [
        "valid_from",
        "valid_to",
        "source_sheet",
        "source_row_range",
        "snapshot_hash",
        "source_file",
    ]
    for field in text_fields:
        if not existing_data.get(field) and incoming_data.get(field):
            existing_data[field] = incoming_data[field]

    if existing_data.get("mode") != incoming_data.get("mode"):
        if existing_data.get("mode") == "SALARIED" and existing_data.get("base_amount") is None:
            existing_data["mode"] = incoming_data.get("mode")
        elif (
            existing_data.get("mode") == "HOURLY"
            and existing_data.get("base_rate") is None
            and incoming_data.get("base_amount") is not None
        ):
            existing_data["mode"] = incoming_data.get("mode")

    if not existing_data.get("raw_snapshot") and incoming_data.get("raw_snapshot"):
        existing_data["raw_snapshot"] = incoming_data["raw_snapshot"]

    return PolicySnapshot(**existing_data)

