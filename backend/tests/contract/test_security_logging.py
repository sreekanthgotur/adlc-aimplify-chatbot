from aimplify_intake.observability.logging import build_safe_log_event


def test_logging_payload_excludes_pii_and_tokens() -> None:
    payload = build_safe_log_event(
        event="submission.processed",
        outcome="accepted",
        request_id="req-123",
        status_code=200,
        token="secret-token",
        email="user@example.com",
        field_value="sensitive content",
    )

    assert payload == {
        "event": "submission.processed",
        "outcome": "accepted",
        "request_id": "req-123",
        "status_code": 200,
    }

