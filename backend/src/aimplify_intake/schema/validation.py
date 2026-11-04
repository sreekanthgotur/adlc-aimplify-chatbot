"""Canonical value validation for extracted candidate fields."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


def validate_field_value(field: dict[str, Any], value: Any) -> str:
    value_type = field.get("value_type")
    if value_type in {"string", "text", "email", "enum"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Field value must be non-empty text.")
        normalized = value.strip()
        if value_type == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Field value does not match the canonical type.")
        if value_type == "enum" and normalized not in field.get("allowed_values", []):
            raise ValueError("Field value does not match the canonical type.")
        return normalized
    if value_type == "boolean" and isinstance(value, bool):
        return "true" if value else "false"
    if value_type == "date" and isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as error:
            raise ValueError("Field value does not match the canonical type.") from error
    raise ValueError("Field value does not match the canonical type.")