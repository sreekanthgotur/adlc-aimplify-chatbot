from io import BytesIO

from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter

from aimplify_intake.api.app import create_app


def _client(*, with_extractor: bool = True) -> TestClient:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=(
            (lambda _text: {"problem_statement": "Policy discovery can be simplified."})
            if with_extractor
            else None
        ),
    )
    client = TestClient(app, headers={"origin": "http://testserver"})
    client.cookies.set("oidc_session", "test-session")
    return client


def test_session_chat_and_field_state_follow_http_contract() -> None:
    with _client() as client:
        created = client.post("/api/v1/sessions")
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert created.json() == {
            "session_id": session_id,
            "status": "in_progress",
            "schema_version": "active",
        }

        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"request_id": "request-1", "text": "An internal assistant improves policy discovery."},
        )
        assert response.status_code == 200
        assert isinstance(response.json()["field_updates"], list)
        assert response.json()["clarification"] is None or isinstance(
            response.json()["clarification"], dict
        )
        assert isinstance(response.json()["status"], str)

        fields = client.get(f"/api/v1/sessions/{session_id}/fields")
        assert fields.status_code == 200
        body = fields.json()
        assert body["schema_version"] == "active"
        assert len(body["sections"]) == 6
        assert sum(len(section["fields"]) for section in body["sections"]) == 27
        assert all("value" not in field or "origin" in field for section in body["sections"] for field in section["fields"])


def test_source_upload_uses_raw_body_and_returns_safe_response() -> None:
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=b"%PDF-1.4 test document",
            headers={"content-type": "application/octet-stream", "x-source-name": "idea.pdf"},
        )

    assert response.status_code in {200, 400, 503}
    if response.status_code == 200:
        assert "field_updates" in response.json()
        assert "idea.pdf" not in response.text


def test_mutating_cookie_request_rejects_untrusted_origin() -> None:
    with _client() as client:
        response = client.post("/api/v1/sessions", headers={"origin": "https://attacker.invalid"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_invalid_chat_error_does_not_echo_submitted_text() -> None:
    private_text = "private-content-" * 2000
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"request_id": "request-invalid", "text": private_text},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_INVALID"
    assert private_text not in response.text


def test_websocket_uses_documented_event_envelopes() -> None:
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        with client.websocket_connect(
            f"/api/v1/sessions/{session_id}/stream",
            headers={"origin": "http://testserver"},
            subprotocols=["aimplify.intake.v1"],
        ) as websocket:
            websocket.send_json(
                {
                    "type": "client.message",
                    "request_id": "request-2",
                    "payload": {"text": "An internal assistant improves policy discovery."},
                }
            )
            events = [websocket.receive_json() for _ in range(3)]
            websocket.send_json(
                {
                    "type": "client.message",
                    "request_id": "request-2",
                    "payload": {"text": "An internal assistant improves policy discovery."},
                }
            )
            replayed_events = [websocket.receive_json() for _ in range(3)]

    assert all(event["type"].startswith("server.") for event in events)
    assert all(event["request_id"] == "request-2" for event in events)
    assert any(event["type"] == "server.submission.status" for event in events)
    assert sum(event["type"] == "server.clarification" for event in events) <= 1
    assert replayed_events == events


def test_websocket_streams_binary_source_then_emits_committed_safe_events() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    pdf = BytesIO()
    writer.write(pdf)
    payload = pdf.getvalue()
    with _client() as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        with client.websocket_connect(
            f"/api/v1/sessions/{session_id}/stream",
            headers={"origin": "http://testserver"},
            subprotocols=["aimplify.intake.v1"],
        ) as websocket:
            websocket.send_json(
                {
                    "type": "client.source.begin",
                    "request_id": "request-begin",
                    "payload": {
                        "source_id": "source-1",
                        "media_type": "application/pdf",
                        "filename": "private.pdf",
                        "size_bytes": len(payload),
                    },
                }
            )
            ready = websocket.receive_json()
            websocket.send_bytes(payload)
            websocket.send_json(
                {
                    "type": "client.source.commit",
                    "request_id": "request-commit",
                    "payload": {"source_id": "source-1"},
                }
            )
            events = [websocket.receive_json() for _ in range(4)]

    assert ready["type"] == "server.source.ready"
    assert [event["type"] for event in events] == [
        "server.field.updated",
        "server.clarification",
        "server.submission.status",
        "server.source.completed",
    ]
    assert all("private.pdf" not in str(event) for event in events)
    assert events[0]["payload"]["value"] == "Policy discovery can be simplified."


def test_unconfigured_extractor_does_not_persist_raw_chat_text() -> None:
    raw_message = "Private source content should not be stored as an extracted field."
    with _client(with_extractor=False) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"request_id": "request-private", "text": raw_message},
        )
        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    assert response.status_code == 200
    assert response.json()["field_updates"] == []
    assert raw_message not in response.text
    assert all("value" not in field for section in fields["sections"] for field in section["fields"])