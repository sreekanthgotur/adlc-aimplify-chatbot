#!/usr/bin/env python
"""CI guard for cloud identity and static credential policies."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

STATIC_CREDENTIAL_ENV_VARS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "AZURE_CLIENT_SECRET",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--trust-config", type=Path, required=True)
    return parser.parse_args()


def validate_no_static_credentials() -> None:
    found = [name for name in STATIC_CREDENTIAL_ENV_VARS if os.getenv(name)]
    if found:
        raise SystemExit(f"Static cloud credentials detected in environment: {', '.join(found)}")


def validate_workflow_oidc(workflow_path: Path) -> None:
    content = workflow_path.read_text(encoding="utf-8")
    if "id-token: write" not in content:
        raise SystemExit("Workflow does not grant id-token: write for OIDC federation.")


def validate_trust_config(trust_path: Path) -> None:
    if not trust_path.exists():
        raise SystemExit("OIDC trust config file is missing.")
    data = json.loads(trust_path.read_text(encoding="utf-8"))
    required = ("provider", "issuer", "audience")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise SystemExit(f"OIDC trust config missing required keys: {', '.join(missing)}")


def main() -> None:
    args = parse_args()
    validate_no_static_credentials()
    validate_workflow_oidc(args.workflow)
    validate_trust_config(args.trust_config)
    print("Cloud identity checks passed.")


if __name__ == "__main__":
    main()

