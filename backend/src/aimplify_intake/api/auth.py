"""OIDC identity validation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def validate_oidc_claims(
    claims: dict[str, Any], *, expected_issuer: str, expected_audience: str
) -> dict[str, Any]:
    issuer = claims.get("iss")
    audience = claims.get("aud")
    subject = claims.get("sub")
    expiry = claims.get("exp")

    if issuer != expected_issuer:
        raise ValueError("Invalid OIDC issuer.")
    if not subject:
        raise ValueError("OIDC subject is required.")
    if isinstance(audience, str):
        valid_audience = audience == expected_audience
    else:
        valid_audience = isinstance(audience, list) and expected_audience in audience
    if not valid_audience:
        raise ValueError("Invalid OIDC audience.")

    now_epoch = int(datetime.now(tz=UTC).timestamp())
    if not isinstance(expiry, int) or expiry <= now_epoch:
        raise ValueError("OIDC token is expired.")

    return {"subject": subject}

