from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from aimplify_intake.persistence.models import FieldValue
from aimplify_intake.persistence.repositories import (
    create_database,
    create_submission,
    persist_ai_values,
    persist_human_values,
)

HUMAN_ONLY_VALUES = {
    "declaration_accepted": True,
    "submitter_signature": "Jordan Lee",
    "date_of_submission": "2026-11-04",
    "reviewer_notes": "Please review this idea.",
}


def _session_and_submission():
    engine, session_factory = create_database("sqlite+pysqlite:///:memory:")
    session = session_factory()
    submission = create_submission(session, "employee-1")
    return engine, session, submission


@pytest.mark.parametrize("field_key,value", HUMAN_ONLY_VALUES.items())
def test_ai_persistence_rejects_all_human_only_fields(field_key: str, value: object) -> None:
    engine, session, submission = _session_and_submission()
    update = {"field_key": field_key, "value": value, "origin": "ai_extracted"}

    with pytest.raises(ValueError, match="not AI-writable"):
        persist_ai_values(session, submission, [update])

    session.close()
    engine.dispose()


@pytest.mark.parametrize("field_key,value", HUMAN_ONLY_VALUES.items())
def test_database_constraint_rejects_ai_origin_human_only_fields(
    field_key: str, value: str
) -> None:
    engine, session, submission = _session_and_submission()
    session.add(
        FieldValue(
            submission_id=submission.submission_id,
            field_key=field_key,
            value="true" if value is True else value,
            origin="ai_extracted",
            updated_at=datetime.now(UTC),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.close()
    engine.dispose()


def test_human_persistence_accepts_explicit_values_for_all_human_only_fields() -> None:
    engine, session, submission = _session_and_submission()

    persist_human_values(session, submission, HUMAN_ONLY_VALUES)

    stored = {
        value.field_key: (value.value, value.origin)
        for value in session.query(FieldValue).all()
    }
    assert stored == {
        field_key: ("true" if value is True else value, "human_entered")
        for field_key, value in HUMAN_ONLY_VALUES.items()
    }
    session.close()
    engine.dispose()