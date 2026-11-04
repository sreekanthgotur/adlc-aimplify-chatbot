# Implementation Plan: AIMPLIFY Conversational Idea Intake

**Branch**: `develop` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification at `specs/001-conversational-intake/spec.md`

> The plan metadata follows the feature branch recorded in `spec.md`. The active
> checkout branch is not changed by this plan.

## Summary

Replace the static idea form with a React conversational interface backed by a
FastAPI service. A LangGraph state machine coordinates chat, in-memory document
and audio ingestion, safe extraction, and clarification turns. Every AI candidate
passes a deterministic, fail-closed NoFacts gate before persistence or display.
PostgreSQL stores the canonical intake schema and accepted values; raw uploads,
transcriptions, and conversation messages are not retained as files or logs.
WebSockets stream turn and safe field-state events, with HTTP endpoints for health,
text submission, and source-upload fallback.

## Technical Context

**Language/Version**: Python 3.11+; TypeScript for the browser client

**Primary Dependencies**: FastAPI, LangGraph, Pydantic, PostgreSQL, uv, React 19,
Vite 6, Tailwind CSS, PyPDF2, python-docx, python-pptx

**Storage**: PostgreSQL for submissions, the versioned schema registry, and
accepted field values only. Uploaded document/audio bytes, raw conversation
messages, and transcription text are transient and are not persisted.

**Testing**: pytest for unit, contract, integration, and golden-evaluation tests;
Vitest and React Testing Library for frontend tests. CI runs at least 50 golden
cases selected by a versioned coverage manifest and blocks merge unless every
case and required coverage category passes.

**Target Platform**: Linux deployment behind an OIDC-enabled ingress configured
not to spool request bodies to disk; browser-based desktop and mobile layouts.

**Project Type**: Web application with Python API and TypeScript frontend

**Performance Goals**: No latency target is defined by the approved specification.
Keep parsing and question generation bounded by upload limits and per-session
concurrency; establish latency SLOs with deployment measurements before launch.

**Constraints**:
- Exactly 27 canonical fields in exactly 6 sections; exactly 18 mandatory fields
  (15 AI-extractable and 3 human-only declarations).
- Declaration Accepted, Date of Submission, and Submitter Signature are
  declaration-only; optional `reviewer_notes` is also human-entry-only.
- Each clarification turn emits no more than one question for one missing mandatory field.
- Uploaded and derived file bytes must not reach disk at any layer, including ingress.
- No PII in application, proxy, WebSocket, or CI logs; cloud identity uses OIDC with
  no static cloud secrets.
- Candidate values containing unverified numbers, percentages, costs, dates, or
  word-form quantities are dropped before persistence or display.
- NoFacts is fail-closed: user-provided source text is not an independent
  verification source. A candidate containing any of those unverified quantities
  is silently dropped even when the quantity appears in the employee's message,
  document, or audio transcription.

**Scale/Scope**: One employee-facing intake application, 3 source modalities,
6 schema sections, 27 canonical fields, 18 mandatory fields, and a CI suite of
at least 50 golden cases. Peak user/upload volume is not specified.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Design gate | Result |
|---|---|---|
| I. Deterministic Safety Gate - NoFacts Pattern | NoFacts runs in ordinary service code on every AI candidate before state update, database write, or client event. Unverifiable quantity-bearing candidates fail closed. | PASS |
| II. Zero-Disk Ephemeral Ingestion | Raw streamed request bodies are bounded and parsed from memory buffers. No multipart `UploadFile`, temporary file, file-backed cache, or persisted source/transcript is allowed. Ingress must also disable disk buffering. | PASS WITH DEPLOYMENT GATE |
| III. Canonical Schema and Human-Only Boundaries | Versioned registry matches the 27 concrete fields and six section assignments in `data-model.md`, with exactly 18 mandatory fields (15 AI-extractable and 3 declaration-only), exactly 9 optional fields, and non-AI-writable declaration and reviewer-note fields. | PASS |
| IV. One Clarification Question per Turn | One graph route selects exactly one missing mandatory field and emits its single approved prompt; no missing mandatory fields means no clarification. | PASS |
| V. Zero-Trust Security and PII Protection | OIDC identity, secure cookie-based WebSocket handshake with Origin validation, no static cloud credentials, and allowlisted non-PII telemetry. | PASS |
| VI. CI Golden Evaluation Gate | CI requires at least 50 versioned cases and 100% pass rate with no skipped cases. | PASS |

No constitutional violation is proposed. The schema inventory is concrete in
`data-model.md`; end-to-end no-disk ingress behavior remains a release gate.

`backend/tests/golden/golden_manifest.json` MUST require scenario coverage for
all six canonical sections, every NoFacts category (numbers, dates, costs,
percentages, and word-form quantities), all three source modalities (chat,
document, audio), single-question pacing (Principle IV), and human-only
protection for `declaration_accepted`, `submitter_signature`, and
`date_of_submission` (Principle III). The golden runner and CI MUST fail if the
manifest, case set, or execution results omit either pacing or human-only
coverage or any other required category.

## Architecture and Failure Modes

### Component topology

```text
Employee browser (React 19 / TypeScript)
  ├─ OIDC-authenticated UI; human-only inputs are separate from AI field updates
  ├─ WebSocket: turn stream and live safe-field state
  └─ HTTP fallback: chat messages and raw streamed source uploads
          │
          ▼
OIDC-aware ingress (TLS, Origin policy, body/concurrency limits, no disk buffering)
          │
          ▼
FastAPI API boundary
  ├─ Authentication, authorization, schema and size validation
  ├─ HTTP health/fallback endpoints and authenticated WebSocket
  └─ Request/session-scoped in-memory source buffers
          │
          ▼
Intake coordinator (LangGraph)
  ├─ chat/document/audio adapters and RAM-only text extraction/transcription
  ├─ canonical field validator
  ├─ deterministic regex + candidate-AST NoFacts gate
  ├─ one-question clarification node using a single field prompt
  └─ persistence boundary: only accepted structured values
          │
          ├─ PostgreSQL: schema registry, submissions, accepted values
          └─ transient model/transcription provider adapter
               (approved no-retention service; OIDC federation where cloud-backed)
```

The application MUST NOT use framework defaults that may spool uploads to disk.
The deployment review MUST verify the complete path from browser through load
balancer/proxy to API, including body buffering, crash dumps, temporary directories,
and provider retention behavior. Audio transcription is an adapter boundary; an
external provider may be used only when its approved configuration provides
no-retention processing and does not require static cloud secrets.

The ingestion contract MUST be verified by an automated test proving that
`Request.stream()` feeds `io.BytesIO` directly, and that a filesystem write trap
fails on any attempted temporary-file spool or source/derived-byte write while
exercising PDF, DOCX, PPTX, WAV, MP3, and WebM. The repository-level contract test
traces the six API upload paths and traps Python file APIs, `os.open`, and tempfile
creation; it passes on the current Windows development environment. This does not
exercise an external ingress process. No reverse proxy or production ingress
configuration is present, so proxy buffering, temporary storage, and proxy log
behavior remain release gates. The security CI gate MUST reject AWS, GCP, or Azure
long-lived cloud credentials and validate the configured OIDC Workload Identity
Federation trust.

### Turn and persistence flow

1. Authenticate the employee and authorize the target submission.
2. Accept chat text or a supported source stream; reject unsupported type, invalid
   length, or over-limit content before parsing. Keep all source bytes in memory.
3. Extract/transcribe transient text and produce candidate values with field keys.
4. Reject AI output targeting human-only fields. Apply deterministic regex
   detectors and candidate-AST traversal for number, percentage, cost, date, and
   word-form quantity patterns to every other candidate.
5. In one transaction, persist only accepted values and safe status metadata.
   Never persist raw documents, audio, transcript, or raw conversation messages.
6. Emit safe field updates and, when any mandatory field remains unfilled,
   exactly one scalar clarification question using that field's approved prompt.
   A rejected candidate is silently omitted from database and events.
7. Release buffers and transient text on completion, failure, disconnect, or timeout.

### Failure modes and required behavior

| Failure | Required behavior |
|---|---|
| Unsupported, malformed, or oversized source | Reject with a generic user-facing error; do not extract, persist, or log source content. Release any in-memory buffer. |
| Parser or transcription provider unavailable | Do not persist partial candidates from the failed source. Report source processing failure without logging content. |
| NoFacts detects an unverified numeric/quantity claim | Silently drop that candidate value. Do not send an event describing or quoting the rejected value. |
| LLM proposes a human-only value | Reject the proposal; keep the field unset by AI and do not emit its value. |
| Question output is missing, multiple, or compound | Do not emit it. Use a deterministic single-field prompt template or report a controlled turn error; never emit multiple questions. |
| Database transaction fails | Emit no field updates as committed; return a retryable error with a non-PII correlation ID. |
| WebSocket disconnects | Cancel source work and release buffers; allow the client to reconnect and retrieve persisted safe field state over authorized HTTP. |
| OIDC validation or authorization fails | Deny before accepting source bytes or returning submission data; log only a non-PII outcome code. |
| Ingress or parser attempts disk buffering | Deployment gate fails; do not release the feature until the end-to-end no-disk path is verified. |

## Project Structure

### Documentation (this feature)

```text
specs/001-conversational-intake/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── websocket.md
    └── intake-http.md
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── src/aimplify_intake/
│   ├── api/                 # HTTP, WebSocket, auth boundary
│   ├── graph/               # LangGraph state and pacing nodes
│   ├── ingestion/           # RAM-only document/audio adapters
│   ├── safety/              # NoFacts gate and candidate validation
│   ├── schema/              # Canonical schema registry and validation
│   ├── persistence/         # PostgreSQL repositories and migrations
│   └── observability/       # PII-free event logging
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    └── golden/
frontend/
├── package.json
├── vite.config.ts
└── src/
    ├── components/          # Chat, source input, and field-state view
    ├── pages/
    ├── services/            # HTTP and WebSocket clients
    └── tests/
```

**Structure Decision**: Separate backend and frontend projects because the
specified Python service and React browser client have independent dependencies
and test runners. The repository currently contains planning artifacts only; this
tree is the proposed implementation layout, not a claim that source directories
already exist.

## Local Validation and Deployment Status

From the repository root, the current CI-equivalent checks are:

```powershell
uv sync --project backend --all-extras
uv run --project backend pytest -q
uv run --project backend python backend/scripts/run_golden_evaluation.py
npm ci --prefix frontend
npm run test --prefix frontend -- --run
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

The API defaults to a 20 MiB upload cap, configurable with `MAX_UPLOAD_BYTES`;
the checked-in `.env.example` sets `20971520`. Uploaded and derived source bytes
and transcripts are transient and are not persisted. Accepted structured values
are persisted, but no accepted-data retention duration or deletion policy is
configured; production release requires an approved duration and implemented
deletion/backup-expiration controls.

The golden runner currently validates manifest coverage and result bookkeeping
for 50 metadata-only case records; its script marks those records passed without
executing model inference. Unit, contract, and integration tests provide the
executable behavior checks in this checkout. The API-to-parser no-disk path is
covered, but end-to-end ingress/proxy behavior and logs are not verified because
no proxy deployment is included. See [the ingress release gate](../../deploy/ingress/README.md).

## Complexity Tracking

No constitution violations or unjustified architectural layers are proposed.
