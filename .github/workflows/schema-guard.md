---
name: Schema Guard
on:
  pull_request:
    branches:
      - main
      - develop
permissions:
  contents: read
  id-token: write
safe-outputs: "add-comment,create-check-run"
---

# Schema Guard Governance Policy

## Scope

Run this policy for pull requests targeting `main` or `develop`. The workflow
must use Ubuntu and Python 3.11, and may read repository contents only. OIDC
token issuance is permitted solely for Cloud Identity Federation validation;
the workflow must not receive production write permissions.

## Required gates

1. Compare the canonical database schema with
   `specs/001-conversational-intake/data-model.md` using the schema-golden
   contract test. Any field, type, enum, section, fill-mode, or count drift
   fails the check.
2. Execute `backend/scripts/run_golden_evaluation.py`. The manifest must
   require and pass the 50-case golden evaluation suite.
3. Execute `.github/scripts/check_cloud_identity.py` against this lockfile and
   `.github/oidc-trust.json`. Reject static cloud credentials and require
   GitHub OIDC Cloud Identity Federation.

## Output and credential controls

The only permitted safe outputs are `add-comment` and `create-check-run`.
These outputs must be mediated by the safe-output mechanism and must not grant
the workflow a production write token. Static cloud secrets are prohibited;
use OIDC federation and the checked-in trust configuration instead.