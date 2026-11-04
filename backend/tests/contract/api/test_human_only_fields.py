from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aimplify_intake.api.app import create_app
from aimplify_intake.services.extraction import extract_safe_candidates

HUMAN_ONLY_VALUES = {
    "declaration_accepted": True,
    "submitter_signature": "Jordan Lee",
    "date_of_submission": "2026-11-04",
    "reviewer_notes": "Please review this idea.",
}


def _client(candidate_extractor: Callable[[str], dict[str, Any]] | None = None) -> TestClient:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=candidate_extractor,
    )
    client = TestClient(app, headers={"origin": "http://testserver"})
    client.cookies.set("oidc_session", "test-session")
    return client


def test_extraction_never_returns_human_only_candidates() -> None:
    candidates = extract_safe_candidates(
        "Please fill in my declaration.", lambda _text: HUMAN_ONLY_VALUES
    )

    assert candidates == []


def test_chat_does_not_suggest_human_only_values() -> None:
    with _client(lambda _text: HUMAN_ONLY_VALUES) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"request_id": "human-only-chat", "text": "Fill in my declaration."},
        )

        assert response.status_code == 200
        assert response.json()["field_updates"] == []
        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    field_values = {
        field["field_key"]: field.get("value")
        for section in fields["sections"]
        for field in section["fields"]
    }
    assert all(field_values[key] is None for key in HUMAN_ONLY_VALUES)


def test_source_upload_does_not_suggest_human_only_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("aimplify_intake.api.app.extract_pdf", lambda _source: "source text")
    with _client(lambda _text: HUMAN_ONLY_VALUES) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=b"in-memory PDF source",
            headers={"content-type": "application/pdf"},
        )

        assert response.status_code == 200
        assert response.json()["field_updates"] == []
        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    assert all(
        field.get("value") is None
        for section in fields["sections"]
        for field in section["fields"]
        if field["field_key"] in HUMAN_ONLY_VALUES
    )


def test_websocket_does_not_emit_human_only_suggestions() -> None:
    with _client(lambda _text: HUMAN_ONLY_VALUES) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        with client.websocket_connect(
            f"/api/v1/sessions/{session_id}/stream",
            headers={"origin": "http://testserver"},
            subprotocols=["aimplify.intake.v1"],
        ) as websocket:
            websocket.send_json(
                {
                    "type": "client.message",
                    "request_id": "human-only-websocket",
                    "payload": {"text": "Fill in my declaration."},
                }
            )
            events = [websocket.receive_json(), websocket.receive_json()]

    assert not any(event["type"] == "server.field.updated" for event in events)
    assert events[-1]["type"] == "server.submission.status"


@pytest.mark.parametrize("field_key,value", HUMAN_ONLY_VALUES.items())
def test_human_field_endpoint_accepts_explicit_human_values(field_key: str, value: Any) -> None:
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.put(
            f"/api/v1/sessions/{session_id}/fields/{field_key}",
            json={"value": value},
        )
        assert response.status_code == 200

        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    saved = {
        field["field_key"]: field
        for section in fields["sections"]
        for field in section["fields"]
    }[field_key]
    assert saved["value"] == ("true" if value is True else value)
    assert saved["origin"] == "human_entered"


def test_human_field_endpoint_rejects_ai_writable_fields() -> None:
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.put(
            f"/api/v1/sessions/{session_id}/fields/idea_title",
            json={"value": "Human entered title"},
        )

    assert response.status_code == 422


def test_human_field_endpoint_requires_authenticated_session() -> None:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    client = TestClient(app, headers={"origin": "http://testserver"})

    response = client.put(
        "/api/v1/sessions/unknown/fields/declaration_accepted",
        json={"value": True},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"