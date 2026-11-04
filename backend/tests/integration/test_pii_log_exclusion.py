import logging
from io import BytesIO

from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter

from aimplify_intake.api.app import create_app


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_http_upload_and_websocket_canaries_do_not_appear_in_server_logs(
    caplog: object,
) -> None:
    canaries = (
        "person@example.com",
        "session-token-canary",
        "private-filename-canary.pdf",
        "private-source-text-canary",
        "private-field-value-canary",
    )
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=lambda _text: {"problem_statement": canaries[-1]},
    )
    caplog.set_level(logging.DEBUG)

    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        client.cookies.set("oidc_session", canaries[1])
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        message = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"request_id": "pii-log-http", "text": f"{canaries[0]} {canaries[3]}"},
        )
        assert message.status_code == 200
        assert canaries[-1] in message.text

        upload = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=_blank_pdf(),
            headers={
                "content-type": "application/pdf",
                "x-source-name": canaries[2],
            },
        )
        assert upload.status_code == 200

        with client.websocket_connect(
            f"/api/v1/sessions/{session_id}/stream",
            headers={"origin": "http://testserver"},
            subprotocols=["aimplify.intake.v1"],
        ) as websocket:
            websocket.send_json(
                {
                    "type": "client.message",
                    "request_id": "pii-log-websocket",
                    "payload": {"text": f"{canaries[0]} {canaries[3]}"},
                }
            )
            for _ in range(3):
                websocket.receive_json()

    captured_logs = "\n".join(
        f"{record.name} {record.__dict__!r}" for record in caplog.records
    )
    assert all(canary not in captured_logs for canary in canaries)