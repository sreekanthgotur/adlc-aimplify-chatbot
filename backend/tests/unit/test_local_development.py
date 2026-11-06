import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from aimplify_intake.main import (
    LOCAL_SESSION_VALUE,
    create_application,
    rule_based_candidate_extractor,
)


def test_local_dev_initializes_first_request_and_extracts_labeled_fields() -> None:
    app = create_application(local_dev_enabled=True)
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        response = client.post(
            "/api/v1/sessions",
            headers={"origin": "http://localhost:5173"},
        )

        assert response.status_code == 201
        assert client.cookies.get("oidc_session") == LOCAL_SESSION_VALUE
        session_id = response.json()["session_id"]

        message_response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            headers={"origin": "http://localhost:5173"},
            json={
                "text": (
                    "Idea Title: Policy assistant\n"
                    "Problem Statement: Policy discovery is difficult."
                )
            },
        )

    assert message_response.status_code == 200
    assert {
        update["field_key"] for update in message_response.json()["field_updates"]
    } == {"idea_title", "problem_statement"}


def test_local_dev_authentication_rejects_non_loopback_clients() -> None:
    app = create_application(local_dev_enabled=True)
    with TestClient(app, client=("192.0.2.1", 12345)) as client:
        response = client.post(
            "/api/v1/sessions",
            headers={"origin": "http://localhost:5173"},
        )

    assert response.status_code == 403
    assert "oidc_session" not in response.headers.get("set-cookie", "")


def test_local_dev_authentication_rejects_non_loopback_websockets() -> None:
    app = create_application(local_dev_enabled=True)
    with (
        TestClient(app, client=("192.0.2.1", 12345)) as client,
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect(
            "/api/v1/sessions/not-used/stream",
            headers={"cookie": f"oidc_session={LOCAL_SESSION_VALUE}"},
        ),
    ):
        pass

    assert error.value.code == 4403


def test_local_authentication_is_disabled_by_default() -> None:
    app = create_application(local_dev_enabled=False)
    with TestClient(app, client=("127.0.0.1", 12345)) as client:
        response = client.post(
            "/api/v1/sessions",
            headers={"origin": "http://localhost:5173"},
        )

    assert response.status_code == 401
    assert "oidc_session" not in response.headers.get("set-cookie", "")


def test_rule_extractor_only_returns_labeled_ai_writable_fields() -> None:
    assert rule_based_candidate_extractor(
        "Idea Title: Policy assistant\n"
        "Problem Statement: Policy discovery is difficult.\n"
        "Declaration Accepted: yes\n"
        "Not A Field: ignored"
    ) == {
        "idea_title": "Policy assistant",
        "problem_statement": "Policy discovery is difficult.",
    }
