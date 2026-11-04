from fastapi.testclient import TestClient

from aimplify_intake.api.app import create_app


def test_unsupported_corrupt_and_oversized_sources_do_not_partially_update_fields() -> None:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        max_upload_bytes=32,
    )
    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        client.cookies.set("oidc_session", "test-session")
        session_id = client.post("/api/v1/sessions").json()["session_id"]

        unsupported = client.post(
            f"/api/v1/sessions/{session_id}/sources/zip", content=b"archive"
        )
        corrupt = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=b"not a PDF",
            headers={"content-type": "application/octet-stream"},
        )
        oversized = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=b"x" * 33,
            headers={"content-type": "application/octet-stream"},
        )
        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    assert unsupported.status_code == 400
    assert corrupt.status_code == 400
    assert oversized.status_code == 413
    assert all("error" in response.json() for response in (unsupported, corrupt, oversized))
    assert all("field" not in item for section in fields["sections"] for item in section["fields"] if "value" in item)