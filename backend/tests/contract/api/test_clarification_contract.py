from fastapi.testclient import TestClient

from aimplify_intake.api.app import create_app


def test_http_turn_returns_one_clarification_object() -> None:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=lambda _text: {},
    )
    client = TestClient(app, headers={"origin": "http://testserver"})
    client.cookies.set("oidc_session", "test-session")
    session_id = client.post("/api/v1/sessions").json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"request_id": "clarification-http", "text": "Start an idea"},
    )

    assert response.status_code == 200
    assert isinstance(response.json()["clarification"], dict)
    assert set(response.json()["clarification"]) == {"field_key", "question"}


def test_websocket_turn_emits_exactly_one_clarification_event() -> None:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=lambda _text: {},
    )
    client = TestClient(app, headers={"origin": "http://testserver"})
    client.cookies.set("oidc_session", "test-session")
    session_id = client.post("/api/v1/sessions").json()["session_id"]

    with client.websocket_connect(
        f"/api/v1/sessions/{session_id}/stream",
        headers={"origin": "http://testserver"},
        subprotocols=["aimplify.intake.v1"],
    ) as websocket:
        websocket.send_json(
            {
                "type": "client.message",
                "request_id": "clarification-ws",
                "payload": {"text": "Start an idea"},
            }
        )
        events = [websocket.receive_json() for _ in range(2)]

    clarification_events = [event for event in events if event["type"] == "server.clarification"]
    assert len(clarification_events) == 1
    assert set(clarification_events[0]["payload"]) == {"field_key", "question"}