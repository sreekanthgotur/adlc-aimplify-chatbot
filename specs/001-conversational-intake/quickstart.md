# Quickstart: AIMPLIFY Conversational Idea Intake

This guide covers local setup and validation for the backend and frontend.
Authenticated intake requires an identity verifier and extraction/transcription
providers to be supplied by the deployment integration; the local entry point
does not configure those providers. Tests inject deterministic local stubs.

## Prerequisites

- Python 3.11 or newer
- `uv`
- Node.js compatible with Vite 6 and npm
- PostgreSQL
- OIDC development identity configuration; do not add static cloud credentials
- Approved transcription/model provider configuration if running audio or AI
  paths; provider retention must meet the project policy

## Start the backend

From the repository root, start PostgreSQL and install the backend including its
test tools:

```powershell
docker compose up -d postgres
uv sync --project backend --all-extras
$env:DATABASE_URL = "postgresql+psycopg://aimplify:change-me@localhost:5432/aimplify"
$env:MAX_UPLOAD_BYTES = "20971520"
Push-Location backend
uv run alembic upgrade head
uv run uvicorn aimplify_intake.main:app --reload
Pop-Location
```

The API upload limit defaults to 20 MiB (`MAX_UPLOAD_BYTES=20971520`) and can be
lowered or raised through environment configuration. Set the ingress limit no
higher than the API limit. The example database password is for local development
only. Keep real credentials out of command history, checked-in files, and logs.

Expected result: the API starts, `GET /health/live` returns `{"status":"live"}`,
and readiness reports available required dependencies. The repository has no
reverse-proxy configuration; the local contract tests verify API streaming and
parser behavior only. Follow [the ingress deployment gate](../../deploy/ingress/README.md)
before deployment. The local entry point has no production OIDC verifier or AI
providers configured, so authenticated user flows require deployment wiring.

## Start the frontend

In another terminal, after frontend source and `package.json` are added:

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

Configure the frontend's local API origin and OIDC development client using
untracked local settings. The WebSocket must use the authenticated same-origin
session and an allowlisted `Origin`.

## Run automated checks

```powershell
uv run --project backend pytest -q
uv run --project backend python backend/scripts/run_golden_evaluation.py
npm ci --prefix frontend
npm run test --prefix frontend -- --run
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

The golden command validates the 50-case manifest, coverage categories, and
result bookkeeping. Its current script supplies pass results for metadata-only
case records; it does not execute model inference. See [the data model](./data-model.md),
[the API contract](./contracts/intake-http.md), and [the WebSocket contract](./contracts/websocket.md)
for invariant details.

## End-to-end validation scenarios

1. **PDF extraction and RAM-only handling**: submit a valid multi-page PDF through
   the raw streamed-source endpoint or WebSocket binary frames; verify safe field
  updates and confirm that application/parser write traps record no attempts.
  Proxy and ingress temporary-file behavior remains unverified until the
  deployment-specific release gate is run.
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

- Configure and verify a no-disk ingress path, including proxy buffering,
  temporary storage, and proxy/access/WebSocket log handling. The repository
  currently contains no ingress implementation.
- Select the approved transcription provider, if external, and verify no-retention
  terms and OIDC federation.
- Wire a production OIDC identity verifier and approved extraction/transcription
  providers; the local ASGI entry point currently has none configured.
- Accepted structured values persist in PostgreSQL, but no retention duration or
  deletion schedule is configured. Approve and implement the accepted-data
  retention period, backup expiration, and deletion workflow before production.
- Choose deployment concurrency limits and response-time SLOs before production
  release.
