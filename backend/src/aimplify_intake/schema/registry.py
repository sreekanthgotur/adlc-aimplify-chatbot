"""Canonical schema loading and invariants."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name("canonical_schema.json")
EXPECTED_FIELD_COUNT = 27
EXPECTED_SECTION_COUNT = 6
EXPECTED_MANDATORY_COUNT = 18
EXPECTED_OPTIONAL_COUNT = 9
DECLARATION_FIELDS = {"declaration_accepted", "submitter_signature", "date_of_submission"}
NON_AI_WRITABLE = DECLARATION_FIELDS | {"reviewer_notes"}


@dataclass(frozen=True)
class PublishedSchema:
    schema_version: str
    sections: list[dict[str, Any]]
    fields: list[dict[str, Any]]


def load_canonical_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = schema_path or SCHEMA_PATH
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("Canonical schema document must be a JSON object.")
    return schema


def validate_schema(schema: dict[str, Any]) -> None:
    sections = schema.get("sections")
    fields = schema.get("fields")
    if not isinstance(sections, list) or not isinstance(fields, list):
        raise ValueError("Schema must contain list-valued 'sections' and 'fields'.")

    if len(sections) != EXPECTED_SECTION_COUNT:
        raise ValueError(f"Expected {EXPECTED_SECTION_COUNT} sections, found {len(sections)}.")
    if len(fields) != EXPECTED_FIELD_COUNT:
        raise ValueError(f"Expected {EXPECTED_FIELD_COUNT} fields, found {len(fields)}.")

    section_keys = [section.get("key") for section in sections]
    if len(set(section_keys)) != EXPECTED_SECTION_COUNT:
        raise ValueError("Section keys must be unique.")

    field_keys = [field.get("key") for field in fields]
    if len(set(field_keys)) != EXPECTED_FIELD_COUNT:
        raise ValueError("Field keys must be unique.")

    mandatory_fields = [field for field in fields if bool(field.get("mandatory"))]
    optional_fields = [field for field in fields if not bool(field.get("mandatory"))]
    if len(mandatory_fields) != EXPECTED_MANDATORY_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_MANDATORY_COUNT} mandatory fields, found {len(mandatory_fields)}."
        )
    if len(optional_fields) != EXPECTED_OPTIONAL_COUNT:
        raise ValueError(f"Expected {EXPECTED_OPTIONAL_COUNT} optional fields, found {len(optional_fields)}.")

    declaration_only = {field["key"] for field in fields if bool(field.get("declaration_only"))}
    if declaration_only != DECLARATION_FIELDS:
        raise ValueError("Declaration-only fields must exactly match canonical declaration fields.")

    ai_blocked = {field["key"] for field in fields if not bool(field.get("ai_writable"))}
    if not NON_AI_WRITABLE.issubset(ai_blocked):
        raise ValueError("Declaration fields and reviewer_notes must be non-AI-writable.")

    for field in fields:
        if field.get("section_key") not in section_keys:
            raise ValueError(f"Field {field.get('key')} references unknown section.")


def publish_schema(schema: dict[str, Any]) -> PublishedSchema:
    validate_schema(schema)
    return PublishedSchema(
        schema_version=str(schema.get("schema_version", "active")),
        sections=list(schema["sections"]),
        fields=list(schema["fields"]),
    )

