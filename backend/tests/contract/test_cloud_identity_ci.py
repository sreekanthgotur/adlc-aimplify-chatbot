import json
import subprocess
import sys
from pathlib import Path


def test_cloud_identity_checker_passes_with_oidc_config() -> None:
    script_path = Path(".github/scripts/check_cloud_identity.py")
    workflow_path = Path(".github/workflows/ci.yml")
    trust_path = Path(".github/oidc-trust.json")

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--workflow",
            str(workflow_path),
            "--trust-config",
            str(trust_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_oidc_trust_config_contains_required_keys() -> None:
    trust_config = json.loads(Path(".github/oidc-trust.json").read_text(encoding="utf-8"))
    assert trust_config["provider"]
    assert trust_config["issuer"]
    assert trust_config["audience"]

