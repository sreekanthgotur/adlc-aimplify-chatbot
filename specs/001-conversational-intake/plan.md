# Implementation Plan: AIMPLIFY Conversational Idea Intake

**Branch**: `main` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification at `specs/001-conversational-intake/spec.md`

> The specification metadata names `develop` as its feature branch, while the
> planning command ran on the current checkout `main`. No branch switch was made.

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
cases and blocks merge unless every case passes.

**Target Platform**: Linux deployment behind an OIDC-enabled ingress configured
not to spool request bodies to disk; browser-based desktop and mobile layouts.

**Project Type**: Web application with Python API and TypeScript frontend

**Performance Goals**: No latency target is defined by the approved specification.
Keep parsing and question generation bounded by upload limits and per-session
concurrency; establish latency SLOs with deployment measurements before launch.

**Constraints**:
- Exactly 27 canonical fields in exactly 6 sections; exactly 18 mandatory fields.
- Declaration Accepted, Date of Submission, and Submitter Signature are human-only.
- Each clarification turn emits no more than one question for one missing mandatory field.
- Uploaded and derived file bytes must not reach disk at any layer, including ingress.
- No PII in application, proxy, WebSocket, or CI logs; cloud identity uses OIDC with
  no static cloud secrets.
- Candidate values containing unverified numbers, percentages, costs, dates, or
  word-form quantities are dropped before persistence or display.

**Scale/Scope**: One employee-facing intake application, 3 source modalities,
6 schema sections, 27 canonical fields, 18 mandatory fields, and a CI suite of
at least 50 golden cases. Peak user/upload volume is not specified.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Design gate | Result |
|---|---|---|
| I. Deterministic Safety Gate - NoFacts Pattern | NoFacts runs in ordinary service code on every AI candidate before state update, database write, or client event. Unverifiable quantity-bearing candidates fail closed. | PASS |
| II. Zero-Disk Ephemeral Ingestion | Raw streamed request bodies are bounded and parsed from memory buffers. No multipart `UploadFile`, temporary file, file-backed cache, or persisted source/transcript is allowed. Ingress must also disable disk buffering. | PASS WITH DEPLOYMENT GATE |
| III. Canonical Schema and Human-Only Boundaries | Versioned schema registry has 27 fields in 6 sections and exactly 18 mandatory fields. AI candidates for the three human-only fields are rejected by service and persistence constraints. Canonical names and section allocation must be supplied from the authoritative intake schema before seed data is finalized. | PASS WITH SCHEMA INPUT GATE |
| IV. One Clarification Question per Turn | One graph route selects exactly one missing mandatory field and emits its single approved prompt; no missing mandatory fields means no clarification. | PASS |
| V. Zero-Trust Security and PII Protection | OIDC identity, secure cookie-based WebSocket handshake with Origin validation, no static cloud credentials, and allowlisted non-PII telemetry. | PASS |
| VI. CI Golden Evaluation Gate | CI requires at least 50 versioned cases and 100% pass rate with no skipped cases. | PASS |

No constitutional violation is proposed. The schema inventory and end-to-end
no-disk ingress behavior are explicit prerequisites for implementation acceptance.

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

## Complexity Tracking

No constitution violations or unjustified architectural layers are proposed.
