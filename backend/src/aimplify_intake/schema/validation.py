"""Canonical value validation for extracted candidate fields."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


def validate_field_policy(field: dict[str, Any]) -> None:
    ai_writable = field.get("ai_writable") is True
    if field.get("declaration_only") is True and ai_writable:
        raise ValueError("Declaration-only fields cannot be AI-writable.")
    if field.get("fill_mode") == "Human only" and ai_writable:
        raise ValueError("Human-entry-only fields cannot be AI-writable.")


def validate_field_origin(field: dict[str, Any], origin: str) -> None:
    validate_field_policy(field)
    ai_writable = field.get("ai_writable") is True
    if origin == "ai_extracted" and not ai_writable:
        raise ValueError("Candidate field is not AI-writable.")
    if origin == "human_entered" and ai_writable:
        raise ValueError("Candidate field is not human-entry-only.")
    if origin not in {"ai_extracted", "human_entered"}:
        raise ValueError("Field origin is invalid.")


def validate_field_value(field: dict[str, Any], value: Any) -> str:
    validate_field_policy(field)
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