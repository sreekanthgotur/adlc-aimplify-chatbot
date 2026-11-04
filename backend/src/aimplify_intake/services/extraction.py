"""Safe candidate extraction and canonical validation orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aimplify_intake.safety.no_facts import no_facts_decision
from aimplify_intake.schema.registry import load_canonical_schema
from aimplify_intake.schema.validation import validate_field_value

CandidateExtractor = Callable[[str], dict[str, Any]]


def _default_candidate_extractor(text: str) -> dict[str, Any]:
    del text
    return {}


def extract_safe_candidates(
    text: str, extractor: CandidateExtractor | None = None
) -> list[dict[str, str]]:
    candidates = (extractor or _default_candidate_extractor)(text)
    schema = load_canonical_schema()
    fields = {field["key"]: field for field in schema["fields"]}
    accepted = []
    for field_key, candidate in candidates.items():
        field = fields.get(field_key)
        if field is None or not field["ai_writable"]:
            continue
        if no_facts_decision(candidate) != "pass":
            continue
        try:
            value = validate_field_value(field, candidate)
        except ValueError:
            continue
        accepted.append({"field_key": field_key, "value": value, "origin": "ai_extracted"})
    return accepted