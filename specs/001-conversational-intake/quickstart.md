# Quickstart: AIMPLIFY Conversational Idea Intake

This guide covers local setup and validation for the planned backend and
frontend. The repository currently contains specifications only; source manifests
and application directories are created during implementation.

## Prerequisites

- Python 3.11 or newer
- `uv`
- Node.js compatible with Vite 6 and npm
- PostgreSQL
- OIDC development identity configuration; do not add static cloud credentials
- Approved transcription/model provider configuration if running audio or AI
  paths; provider retention must meet the project policy

## Start the backend

From the repository root, after backend source and `pyproject.toml` are added:

```powershell
Set-Location backend
uv sync --dev
uv run alembic upgrade head
uv run uvicorn aimplify_intake.main:app --reload
```

Supply database and OIDC settings through local environment configuration that is
excluded from version control. Do not put credentials or user content in command
arguments, checked-in files, or logs. Configure the local ingress/server path to
avoid disk request buffering before testing uploads.

Expected result: the API starts, `GET /health/live` returns `{"status":"live"}`,
and readiness reports available required dependencies.

## Start the frontend

In another terminal, after frontend source and `package.json` are added:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Configure the frontend's local API origin and OIDC development client using
untracked local settings. The WebSocket must use the authenticated same-origin
session and an allowlisted `Origin`.

## Run automated checks

```powershell
Set-Location backend
uv run pytest

Set-Location ..\frontend
npm test -- --run
```

The CI job must additionally run the complete golden suite, confirm at least 50
cases are present, fail on skipped/omitted cases, and require a 100% pass rate.
See [the data model](./data-model.md) and [the API contracts](./contracts/intake-http.md)
and [WebSocket contract](./contracts/websocket.md) for invariant details.

## End-to-end validation scenarios

1. **PDF extraction and RAM-only handling**: submit a valid multi-page PDF through
   the raw streamed-source endpoint or WebSocket binary frames; verify safe field
   updates and confirm that no application, parser, proxy, or ingress temporary
   file contains source bytes.
2. **NoFacts adversarial claims**: submit claims containing digits, percentages,
   costs, dates, and word-form quantities; verify no such candidate appears in
   persisted values or client events.
3. **Clarification pacing**: submit an idea missing multiple mandatory fields;
   verify each response/turn has zero or one clarification object and each
   clarification asks about one field only.
4. **Human-only fields**: ask the assistant to fill Declaration Accepted,
   Submitter Signature, or Date of Submission; verify no AI update is returned
   and persistence rejects an AI-origin write.
5. **Audio and other documents**: exercise DOCX, PPTX, WAV, MP3, and WebM; verify
   processing is memory-only and source/transcript buffers are released.
6. **Security and CI**: verify PII/token canaries do not appear in application,
   proxy, or WebSocket logs; validate OIDC-only cloud identity; fail the CI gate
   for one failing or omitted golden case.

## Release blockers

- Import the authoritative 27-field inventory, all types and six section
  assignments, and exactly 18 mandatory flags before generating schema migrations.
- Configure and verify a no-disk ingress path, including proxy buffering and
  temporary storage behavior.
- Select the approved transcription provider, if external, and verify no-retention
  terms and OIDC federation.
- Choose deployment upload/concurrency limits, accepted-data retention, and
  response-time SLOs before production release.
