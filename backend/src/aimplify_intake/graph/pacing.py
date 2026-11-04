"""Single-question pacing helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClarificationDecision:
    field_key: str
    question: str


def select_next_clarification(
    canonical_fields: list[dict[str, Any]], current_values: dict[str, Any]
) -> ClarificationDecision | None:
    for field in canonical_fields:
        if not field.get("mandatory"):
            continue
        key = field["key"]
        value = current_values.get(key)
        if value in (None, ""):
            question = field.get("clarification_prompt")
            if not question:
                raise ValueError(f"Mandatory field {key} has no clarification prompt.")
            return ClarificationDecision(field_key=key, question=question)
    return None

