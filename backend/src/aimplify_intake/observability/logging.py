"""Allowlist-only logging helpers."""

from __future__ import annotations

from typing import Any

SAFE_KEYS = {"event", "outcome", "request_id", "status_code"}


def build_safe_log_event(event: str, outcome: str, request_id: str, **extras: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"event": event, "outcome": outcome, "request_id": request_id}
    for key, value in extras.items():
        if key in SAFE_KEYS:
            payload[key] = value
    return payload

