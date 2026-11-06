import pytest
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from aimplify_intake.api.oidc import (
    EntraConfig,
    add_oidc_middleware,
    create_oidc_router,
    create_session_codec,
)
from aimplify_intake.main import create_application

TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CLIENT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _config() -> EntraConfig:
    return EntraConfig(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret="test-client-secret",
        session_signing_key="session-signing-key-that-is-at-least-32-bytes",
        flow_signing_key="flow-signing-key-that-is-at-least-32-bytes",
        app_origin="https://intake.example.test",
    )


def test_entra_session_is_signed_and_tenant_bound() -> None:
    config = _config()
    serializer, verify = create_session_codec(config)
    cookie = serializer.dumps({"sub": "employee-object-id", "tid": TENANT_ID})

    assert verify(cookie) == {"subject": f"{TENANT_ID}:employee-object-id"}

    wrong_tenant = serializer.dumps(
        {"sub": "employee-object-id", "tid": "cccccccc-cccc-4ccc-8ccc-cccccccccccc"}
    )
    with pytest.raises(ValueError, match="Unauthenticated"):
        verify(wrong_tenant)


def test_entra_session_rejects_tampering() -> None:
    _serializer, verify = create_session_codec(_config())

    with pytest.raises(ValueError, match="Unauthenticated"):
        verify("tampered-session-cookie")


def test_entra_configuration_requires_complete_https_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT_ID)
    monkeypatch.delenv("ENTRA_CLIENT_ID", raising=False)
    monkeypatch.delenv("ENTRA_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_SESSION_SIGNING_KEY", raising=False)
    monkeypatch.delenv("OIDC_FLOW_SIGNING_KEY", raising=False)
    monkeypatch.delenv("APP_ORIGIN", raising=False)

    with pytest.raises(RuntimeError, match="Incomplete Entra configuration"):
        EntraConfig.from_environment()


def test_auth_status_and_unconfigured_login_fail_closed() -> None:
    app = create_application(local_dev_enabled=False)
    with TestClient(app) as client:
        assert client.get("/auth/status").json() == {"authenticated": False}
        response = client.get("/auth/login")

    assert response.status_code == 503


def test_production_entrypoint_requires_oidc_and_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "ENTRA_TENANT_ID",
        "ENTRA_CLIENT_ID",
        "ENTRA_CLIENT_SECRET",
        "OIDC_SESSION_SIGNING_KEY",
        "OIDC_FLOW_SIGNING_KEY",
        "APP_ORIGIN",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AIMPLIFY_LOCAL_DEV", raising=False)

    with pytest.raises(RuntimeError, match="complete Microsoft Entra configuration"):
        create_application()


def test_production_requires_explicit_aws_data_processing_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("ENTRA_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("ENTRA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OIDC_SESSION_SIGNING_KEY", "session-signing-key-that-is-at-least-32-bytes")
    monkeypatch.setenv("OIDC_FLOW_SIGNING_KEY", "flow-signing-key-that-is-at-least-32-bytes")
    monkeypatch.setenv("APP_ORIGIN", "https://intake.example.test")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://intake.example.test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/aimplify")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.delenv("AIMPLIFY_LOCAL_DEV", raising=False)
    monkeypatch.delenv("BEDROCK_DATA_PROCESSING_APPROVED", raising=False)
    monkeypatch.delenv("TRANSCRIBE_NO_RETENTION_APPROVED", raising=False)

    with pytest.raises(RuntimeError, match="Bedrock data-processing approval"):
        create_application()

    monkeypatch.setenv("BEDROCK_DATA_PROCESSING_APPROVED", "true")
    with pytest.raises(RuntimeError, match="Transcribe no-retention approval"):
        create_application()


def test_entra_login_redirect_uses_configured_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    captured_redirect_uri = ""
    captured_client_options: dict[str, object] = {}

    class FakeEntra:
        async def authorize_redirect(self, _request: object, redirect_uri: str) -> RedirectResponse:
            nonlocal captured_redirect_uri
            captured_redirect_uri = redirect_uri
            assert redirect_uri == config.redirect_uri
            return RedirectResponse("https://login.microsoftonline.com/test", status_code=302)

    def fake_register(self: OAuth, name: str, **kwargs: object) -> None:
        captured_client_options.update(kwargs)
        setattr(self, name, FakeEntra())

    monkeypatch.setattr(OAuth, "register", fake_register)
    router = create_oidc_router(
        config,
        create_session_codec(config)[1],
        {"https://intake.example.test"},
    )
    app = FastAPI()
    app.include_router(router)
    add_oidc_middleware(app, config)

    with TestClient(app, base_url="https://intake.example.test") as client:
        response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 302
    assert "login.microsoftonline.com" in response.headers["location"]
    assert captured_redirect_uri == "https://intake.example.test/auth/callback"
    assert captured_client_options["token_endpoint_auth_method"] == "client_secret_post"
    assert captured_client_options["client_kwargs"] == {"scope": "openid"}


def test_entra_callback_issues_secure_tenant_bound_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()

    class FakeEntra:
        async def authorize_access_token(self, _request: object) -> dict[str, object]:
            return {"userinfo": {"sub": "employee-object-id", "tid": TENANT_ID}}

    def fake_register(self: OAuth, name: str, **_kwargs: object) -> None:
        setattr(self, name, FakeEntra())

    monkeypatch.setattr(OAuth, "register", fake_register)
    router = create_oidc_router(
        config,
        create_session_codec(config)[1],
        {"https://intake.example.test"},
    )
    app = FastAPI()
    app.include_router(router)
    add_oidc_middleware(app, config)

    with TestClient(app, base_url="https://intake.example.test") as client:
        response = client.get(
            "/auth/callback?code=fake&state=fake",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.cookies.get("oidc_session")
    assert cookie
    assert create_session_codec(config)[1](cookie) == {
        "subject": f"{TENANT_ID}:employee-object-id"
    }
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie


def test_logout_checks_origin_and_redirects_to_tenant_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()

    def fake_register(self: OAuth, name: str, **_kwargs: object) -> None:
        setattr(self, name, object())

    monkeypatch.setattr(OAuth, "register", fake_register)
    app = FastAPI()
    app.include_router(
        create_oidc_router(
            config,
            create_session_codec(config)[1],
            {"https://intake.example.test"},
        )
    )
    add_oidc_middleware(app, config)

    with TestClient(app, base_url="https://intake.example.test") as client:
        denied = client.post(
            "/auth/logout",
            headers={"origin": "https://attacker.example.test"},
        )
        response = client.post(
            "/auth/logout",
            headers={"origin": "https://intake.example.test"},
            follow_redirects=False,
        )

    assert denied.status_code == 403
    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "https://login.microsoftonline.com/"
    )
    assert "post_logout_redirect_uri=https%3A%2F%2Fintake.example.test%2F" in response.headers["location"]
