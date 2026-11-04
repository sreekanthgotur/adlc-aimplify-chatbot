"""Transactional persistence operations for intake sessions and safe values."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aimplify_intake.persistence.models import (
    Base,
    CanonicalFieldDefinition,
    FieldValue,
    IdeaSubmission,
    IntakeSection,
    SchemaVersion,
)
from aimplify_intake.schema.registry import load_canonical_schema, publish_schema
from aimplify_intake.schema.validation import validate_field_value

NON_AI_WRITABLE = {"declaration_accepted", "submitter_signature", "date_of_submission", "reviewer_notes"}


def create_database(database_url: str) -> tuple[Engine, sessionmaker[Session]]:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def ensure_canonical_schema(session: Session) -> None:
    schema = publish_schema(load_canonical_schema())
    if session.get(SchemaVersion, schema.schema_version) is not None:
        return
    session.add(
        SchemaVersion(
            schema_version=schema.schema_version,
            published_at=datetime.now(UTC),
            field_count=len(schema.fields),
            section_count=len(schema.sections),
            mandatory_count=sum(bool(field["mandatory"]) for field in schema.fields),
        )
    )
    session.add_all(
        IntakeSection(
            schema_version=schema.schema_version,
            section_key=section["key"],
            name=section["name"],
            ordinal=section["ordinal"],
        )
        for section in schema.sections
    )
    session.add_all(
        CanonicalFieldDefinition(
            schema_version=schema.schema_version,
            field_key=field["key"],
            display_name=field["display_name"],
            section_key=field["section_key"],
            value_type=field["value_type"],
            mandatory=field["mandatory"],
            fill_mode=field["fill_mode"],
            ai_writable=field["ai_writable"],
            declaration_only=field["declaration_only"],
            clarification_prompt=field["clarification_prompt"],
        )
        for field in schema.fields
    )
    session.commit()


def create_submission(session: Session, subject_ref: str) -> IdeaSubmission:
    ensure_canonical_schema(session)
    submission = IdeaSubmission(
        submission_id=uuid4().hex,
        schema_version="active",
        subject_ref=subject_ref,
        status="in_progress",
    )
    session.add(submission)
    session.commit()
    return submission


def get_authorized_submission(session: Session, submission_id: str, subject_ref: str) -> IdeaSubmission | None:
    submission = session.get(IdeaSubmission, submission_id)
    if submission is None or submission.subject_ref != subject_ref:
        return None
    return submission


def read_field_state(session: Session, submission: IdeaSubmission) -> dict[str, object]:
    schema = publish_schema(load_canonical_schema())
    values = {
        item.field_key: item
        for item in session.scalars(
            select(FieldValue).where(FieldValue.submission_id == submission.submission_id)
        )
    }
    sections = []
    for section in schema.sections:
        fields = []
        for definition in schema.fields:
            if definition["section_key"] != section["key"]:
                continue
            value = values.get(definition["key"])
            field_state: dict[str, object] = {
                "field_key": definition["key"],
                "mandatory": definition["mandatory"],
                "human_only": not definition["ai_writable"],
            }
            if value is not None:
                field_state.update({"value": value.value, "origin": value.origin})
            fields.append(field_state)
        sections.append({"section_key": section["key"], "fields": fields})
    return {
        "session_id": submission.submission_id,
        "schema_version": submission.schema_version,
        "sections": sections,
        "status": submission.status,
    }


def persist_ai_values(session: Session, submission: IdeaSubmission, updates: list[dict[str, str]]) -> None:
    schema = publish_schema(load_canonical_schema())
    definitions = {field["key"]: field for field in schema.fields}
    validated = []
    for update in updates:
        field_key = update["field_key"]
        definition = definitions.get(field_key)
        if definition is None or not definition["ai_writable"] or field_key in NON_AI_WRITABLE:
            raise ValueError("Candidate field is not AI-writable.")
        validated.append((field_key, validate_field_value(definition, update["value"])))
    try:
        for field_key, value in validated:
            current = session.scalar(
                select(FieldValue).where(
                    FieldValue.submission_id == submission.submission_id,
                    FieldValue.field_key == field_key,
                )
            )
            if current is None:
                session.add(
                    FieldValue(
                        submission_id=submission.submission_id,
                        field_key=field_key,
                        value=value,
                        origin="ai_extracted",
                    )
                )
            else:
                current.value = value
                current.origin = "ai_extracted"
                current.updated_at = datetime.now(UTC)
        session.commit()
    except Exception:
        session.rollback()
        raise