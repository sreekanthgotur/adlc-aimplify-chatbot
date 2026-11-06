"""ASGI entry point and opt-in local development authentication."""

from __future__ import annotations

import ipaddress
import os
import re
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from aimplify_intake.api.app import create_app
from aimplify_intake.api.oidc import (
    EntraConfig,
    add_oidc_middleware,
    create_oidc_router,
    create_session_codec,
)
from aimplify_intake.ingestion.audio import TranscriptionProvider
from aimplify_intake.schema.registry import load_canonical_schema
from aimplify_intake.services.aws_providers import (
    create_bedrock_candidate_extractor,
    create_transcribe_provider,
)

LOCAL_SESSION_COOKIE = "oidc_session"
LOCAL_SESSION_VALUE = "dev-local-session"
FIELD_LINE = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z _-]*)\s*:\s*(.*?)\s*$")


def local_identity_verifier(_cookie: str | None) -> dict[str, str]:
    if _cookie != LOCAL_SESSION_VALUE:
        raise ValueError("Invalid local development session.")
    return {"subject": "developer@aimplify.internal"}


def rule_based_candidate_extractor(text: str) -> dict[str, Any]:
    """Extract explicitly labeled canonical fields without calling an external model."""
    known_fields = {
        field["key"]
        for field in load_canonical_schema()["fields"]
        if field["ai_writable"]
    }
    candidates: dict[str, Any] = {}
    for line in text.splitlines():
        match = FIELD_LINE.fullmatch(line)
        if not match:
            continue
        field_key = re.sub(r"[^a-z0-9]+", "_", match.group(1).lower()).strip("_")
        value = match.group(2).strip()
        if field_key in known_fields and value:
            candidates[field_key] = value
    return candidates


class LocalDevSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        cookie_missing = request.cookies.get(LOCAL_SESSION_COOKIE) is None
        if cookie_missing:
            headers = list(request.scope["headers"])
            cookie_header = b"; ".join(
                value for name, value in headers if name.lower() == b"cookie"
            )
            headers = [
                (name, value)
                for name, value in headers
                if name.lower() != b"cookie"
            ]
            headers.append(
                (
                    b"cookie",
                    cookie_header
                    + (b"; " if cookie_header else b"")
                    + f"{LOCAL_SESSION_COOKIE}={LOCAL_SESSION_VALUE}".encode("ascii"),
                )
            )
            request.scope["headers"] = headers

        response = await call_next(request)
        if cookie_missing:
            response.set_cookie(
                LOCAL_SESSION_COOKIE,
                LOCAL_SESSION_VALUE,
                httponly=True,
                secure=False,
                samesite="lax",
                path="/",
            )
        return response


class LocalDevLoopbackMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        try:
            is_loopback = client is not None and ipaddress.ip_address(client[0]).is_loopback
        except ValueError:
            is_loopback = False
        if is_loopback:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4403})
            return

        body = b'{"detail":"Local development authentication is loopback-only."}'
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def create_application(*, local_dev_enabled: bool | None = None) -> FastAPI:
    if local_dev_enabled is None:
        local_dev_enabled = os.getenv("AIMPLIFY_LOCAL_DEV") == "1"
    app_environment = os.getenv("APP_ENV", "development").lower()
    entra_config = EntraConfig.from_environment()
    if local_dev_enabled and (app_environment == "production" or entra_config is not None):
        raise RuntimeError("Local development authentication cannot be enabled with production OIDC.")
    if app_environment == "production" and entra_config is None:
        raise RuntimeError("Production requires a complete Microsoft Entra configuration.")
    if app_environment == "production" and not os.getenv("DATABASE_URL", "").startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")

    candidate_extractor: Callable[[str], dict[str, Any]] | None = None
    transcription_provider: TranscriptionProvider | None = None
    transcription_no_retention_approved = False
    if local_dev_enabled:
        candidate_extractor = rule_based_candidate_extractor
    elif app_environment == "production":
        aws_region = os.getenv("AWS_REGION", "").strip()
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
        if not aws_region or not bedrock_model_id:
            raise RuntimeError("Production requires AWS_REGION and BEDROCK_MODEL_ID.")
        if os.getenv("BEDROCK_DATA_PROCESSING_APPROVED") != "true":
            raise RuntimeError("Production requires explicit Bedrock data-processing approval.")
        if os.getenv("TRANSCRIBE_NO_RETENTION_APPROVED") != "true":
            raise RuntimeError("Production requires explicit Transcribe no-retention approval.")
        candidate_extractor = create_bedrock_candidate_extractor(
            aws_region, bedrock_model_id
        )
        transcription_provider = create_transcribe_provider(
            aws_region, os.getenv("TRANSCRIBE_LANGUAGE_CODE", "en-IN").strip()
        )
        transcription_no_retention_approved = True

    allowed_origins = {
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    }
    if entra_config is not None and entra_config.app_origin not in allowed_origins:
        raise RuntimeError("ALLOWED_ORIGINS must include APP_ORIGIN.")

    identity_verifier: Callable[[str | None], dict[str, Any]] | None = None
    if local_dev_enabled:
        identity_verifier = local_identity_verifier
    elif entra_config is not None:
        _serializer, identity_verifier = create_session_codec(entra_config)

    app = create_app(
        identity_verifier=identity_verifier,
        candidate_extractor=candidate_extractor,
        transcription_provider=transcription_provider,
        transcription_no_retention_approved=transcription_no_retention_approved,
        allowed_origins=allowed_origins or None,
    )
    app.include_router(
        create_oidc_router(
            entra_config,
            identity_verifier,
            allowed_origins or {"http://localhost:5173"},
        )
    )
    if entra_config is not None:
        add_oidc_middleware(app, entra_config)
    if local_dev_enabled:
        app.add_middleware(LocalDevSessionMiddleware)
        app.add_middleware(LocalDevLoopbackMiddleware)
    return app


app = create_application()
