# Quickstart: AIMPLIFY Conversational Idea Intake

This guide covers local setup and validation for the backend and frontend.
Production authentication supports single-tenant Microsoft Entra ID when its
required environment variables are configured. Local development can opt into
a loopback-only fixed identity with `AIMPLIFY_LOCAL_DEV=1`; this is not OIDC and
must never be used in a deployed environment. Production uses Amazon Bedrock
for text extraction and Amazon Transcribe streaming for audio; both require
explicit AWS configuration and data-processing approval.

## Prerequisites

- Python 3.12 or newer
- `uv`
- Node.js compatible with Vite 6 and npm
- PostgreSQL
- Use local development authentication only on loopback; do not add static cloud credentials
- Approved Bedrock and Transcribe data-processing settings before enabling
  production AI or audio paths

## Start the backend

From the repository root, start PostgreSQL and install the backend including its
test tools:

```powershell
docker compose up -d postgres
uv sync --project backend --all-extras
$env:DATABASE_URL = "postgresql+psycopg://aimplify:change-me@localhost:5432/aimplify"
$env:MAX_UPLOAD_BYTES = "20971520"
$env:AIMPLIFY_LOCAL_DEV = "1"
Push-Location backend
uv run alembic upgrade head
uv run uvicorn aimplify_intake.main:app --reload --reload-dir src
Pop-Location
```

The API upload limit defaults to 20 MiB (`MAX_UPLOAD_BYTES=20971520`) and can be
lowered or raised through environment configuration. Set the ingress limit no
higher than the API limit. The example database password is for local development
only. Keep real credentials out of command history, checked-in files, and logs.
The local identity bypass is restricted to loopback traffic. Never expose this
backend on a LAN or set `AIMPLIFY_LOCAL_DEV` in AWS.

Expected result: the API starts, `GET /health/live` returns `{"status":"live"}`,
and readiness reports available required dependencies. The repository has no
reverse-proxy configuration; the local contract tests verify API streaming and
parser behavior only. Follow [the ingress deployment gate](../../deploy/ingress/README.md)
before deployment. For Entra and AWS production configuration, see
[the AWS deployment preparation guide](../../deploy/aws/README.md).

## Start the frontend

In another terminal, install frontend dependencies and start the application:

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

The golden command executes 50 deterministic case inputs through chat, PDF, or
audio HTTP intake using injected test extraction and transcription providers.
Each case checks expected accepted and rejected field updates, persisted values,
human-only omissions, and clarification count; the runner also enforces required
modality and NoFacts-category coverage. It does not call an external model or
production provider. See [the data model](./data-model.md), [the API contract](./contracts/intake-http.md),
and [the WebSocket contract](./contracts/websocket.md) for invariant details.

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
   processing is memory-only and source/transcript buffers are released. In
   production, FFmpeg converts audio through stdin/stdout pipes to Transcribe's
   streaming PCM format; no S3 staging or temporary audio files are used.
6. **Security and CI**: verify PII/token canaries do not appear in application,
   proxy, or WebSocket logs; validate OIDC-only cloud identity; fail the CI gate
   for one failing or omitted golden case.

## Release blockers

- Configure and verify a no-disk ingress path, including proxy buffering,
  temporary storage, and proxy/access/WebSocket log handling. The repository
  currently contains no ingress implementation.
- Set `AWS_REGION`, an available `BEDROCK_MODEL_ID`, and
  `TRANSCRIBE_LANGUAGE_CODE` for the deployment. The container uses Python 3.12
  and includes FFmpeg for in-memory audio conversion.
- Before setting `BEDROCK_DATA_PROCESSING_APPROVED` or
  `TRANSCRIBE_NO_RETENTION_APPROVED`, have the AWS and company administrators
  verify model terms, service data handling, Bedrock invocation logging and
  retention settings in the selected region. The code requires explicit
  approval but cannot inspect account-level settings.
- Verify the ECS task role is restricted to the selected Bedrock model and
  Transcribe streaming action. Do not configure static AWS access keys.
- Accepted structured values persist in PostgreSQL, but no retention duration or
  deletion schedule is configured. Approve and implement the accepted-data
  retention period, backup expiration, and deletion workflow before production.
- Choose deployment concurrency limits and response-time SLOs before production
  release.
