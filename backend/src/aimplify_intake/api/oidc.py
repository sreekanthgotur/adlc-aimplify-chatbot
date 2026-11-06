"""Microsoft Entra ID login and signed browser-session handling."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from authlib.integrations.base_client.errors import OAuthError  # type: ignore[import-untyped]
from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from httpx import HTTPError
from itsdangerous import BadData, URLSafeTimedSerializer
from joserfc.errors import JoseError
from starlette.middleware.sessions import SessionMiddleware

SESSION_COOKIE = "oidc_session"
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
FLOW_SESSION_MAX_AGE_SECONDS = 10 * 60
CALLBACK_PATH = "/auth/callback"

IdentityVerifier = Callable[[str | None], dict[str, str]]


@dataclass(frozen=True)
class EntraConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    session_signing_key: str
    flow_signing_key: str
    app_origin: str

    @classmethod
    def from_environment(cls) -> EntraConfig | None:
        names = {
            "ENTRA_TENANT_ID": os.getenv("ENTRA_TENANT_ID", "").strip(),
            "ENTRA_CLIENT_ID": os.getenv("ENTRA_CLIENT_ID", "").strip(),
            "ENTRA_CLIENT_SECRET": os.getenv("ENTRA_CLIENT_SECRET", "").strip(),
            "OIDC_SESSION_SIGNING_KEY": os.getenv("OIDC_SESSION_SIGNING_KEY", ""),
            "OIDC_FLOW_SIGNING_KEY": os.getenv("OIDC_FLOW_SIGNING_KEY", ""),
            "APP_ORIGIN": os.getenv("APP_ORIGIN", "").strip(),
        }
        configured = {key: value for key, value in names.items() if value}
        if not configured:
            return None
        missing = sorted(set(names) - set(configured))
        if missing:
            raise RuntimeError(
                "Incomplete Entra configuration; missing: " + ", ".join(missing)
            )

        try:
            tenant_id = str(UUID(names["ENTRA_TENANT_ID"]))
            client_id = str(UUID(names["ENTRA_CLIENT_ID"]))
        except ValueError as error:
            raise RuntimeError("Entra tenant and client IDs must be UUIDs.") from error

        origin = urlsplit(names["APP_ORIGIN"])
        if (
            origin.scheme != "https"
            or not origin.netloc
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username
            or origin.password
        ):
            raise RuntimeError("APP_ORIGIN must be an HTTPS origin with no path.")
        if len(names["OIDC_SESSION_SIGNING_KEY"].encode("utf-8")) < 32:
            raise RuntimeError("OIDC_SESSION_SIGNING_KEY must be at least 32 bytes.")
        if len(names["OIDC_FLOW_SIGNING_KEY"].encode("utf-8")) < 32:
            raise RuntimeError("OIDC_FLOW_SIGNING_KEY must be at least 32 bytes.")

        return cls(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=names["ENTRA_CLIENT_SECRET"],
            session_signing_key=names["OIDC_SESSION_SIGNING_KEY"],
            flow_signing_key=names["OIDC_FLOW_SIGNING_KEY"],
            app_origin=names["APP_ORIGIN"].rstrip("/"),
        )

    @property
    def redirect_uri(self) -> str:
        return f"{self.app_origin}{CALLBACK_PATH}"


def create_session_codec(
    config: EntraConfig,
) -> tuple[URLSafeTimedSerializer, IdentityVerifier]:
    serializer = URLSafeTimedSerializer(
        config.session_signing_key,
        salt="aimplify-entra-session-v1",
        signer_kwargs={"digest_method": sha256},
    )

    def verify_session(cookie: str | None) -> dict[str, str]:
        if not cookie:
            raise ValueError("Unauthenticated.")
        try:
            claims = serializer.loads(cookie, max_age=SESSION_MAX_AGE_SECONDS)
        except BadData as error:
            raise ValueError("Unauthenticated.") from error
        if not isinstance(claims, dict):
            raise TypeError("Unauthenticated.")
        subject = claims.get("sub")
        tenant = claims.get("tid")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Unauthenticated.")
        if tenant != config.tenant_id:
            raise ValueError("Unauthenticated.")
        return {"subject": f"{tenant}:{subject}"}

    return serializer, verify_session


def add_oidc_middleware(app: FastAPI, config: EntraConfig) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.flow_signing_key,
        session_cookie="aimplify_oidc_flow",
        max_age=FLOW_SESSION_MAX_AGE_SECONDS,
        same_site="lax",
        https_only=True,
    )


def create_oidc_router(
    config: EntraConfig | None,
    identity_verifier: IdentityVerifier | None,
    allowed_origins: set[str],
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["authentication"])
    oauth = None
    serializer = None
    if config is not None:
        oauth = OAuth()
        oauth.register(
            name="entra",
            client_id=config.client_id,
            client_secret=config.client_secret,
            server_metadata_url=(
                "https://login.microsoftonline.com/"
                f"{config.tenant_id}/v2.0/.well-known/openid-configuration"
            ),
            token_endpoint_auth_method="client_secret_post",
            client_kwargs={"scope": "openid"},
        )
        serializer, _ = create_session_codec(config)

    @router.get("/status")
    async def auth_status(request: Request, response: Response) -> dict[str, bool]:
        response.headers["Cache-Control"] = "no-store"
        if identity_verifier is None:
            return {"authenticated": False}
        try:
            identity_verifier(request.cookies.get(SESSION_COOKIE))
        except (ValueError, BadData):
            return {"authenticated": False}
        return {"authenticated": True}

    @router.get("/login")
    async def login(request: Request) -> Response:
        if config is None or oauth is None:
            raise HTTPException(status_code=503, detail="Sign-in is not configured.")
        response = await oauth.entra.authorize_redirect(request, config.redirect_uri)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @router.get("/callback")
    async def callback(request: Request) -> Response:
        if config is None or oauth is None or serializer is None:
            raise HTTPException(status_code=503, detail="Sign-in is not configured.")
        try:
            token = await oauth.entra.authorize_access_token(request)
        except (HTTPError, OAuthError, JoseError) as error:
            raise HTTPException(status_code=401, detail="Sign-in could not be completed.") from error

        claims = token.get("userinfo")
        if not isinstance(claims, Mapping):
            raise HTTPException(status_code=401, detail="Sign-in could not be completed.")
        subject = claims.get("sub")
        tenant_id = claims.get("tid")
        if (
            not isinstance(subject, str)
            or not subject
            or tenant_id != config.tenant_id
        ):
            raise HTTPException(status_code=401, detail="Sign-in could not be completed.")

        session_cookie = serializer.dumps({"sub": subject, "tid": tenant_id})
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            session_cookie,
            max_age=SESSION_MAX_AGE_SECONDS,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @router.post("/logout")
    async def logout(request: Request) -> Response:
        if request.headers.get("origin") not in allowed_origins:
            raise HTTPException(status_code=403, detail="Forbidden.")
        logout_url = (
            "https://login.microsoftonline.com/"
            f"{config.tenant_id}/oauth2/v2.0/logout?"
            + urlencode({"post_logout_redirect_uri": f"{config.app_origin}/"})
            if config is not None
            else "/"
        )
        response = RedirectResponse(logout_url, status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        response.delete_cookie(
            "aimplify_oidc_flow",
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return router
