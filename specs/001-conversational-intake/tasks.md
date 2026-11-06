---
description: "TDD task list for AIMPLIFY Conversational Idea Intake"
---

# Tasks: AIMPLIFY Conversational Idea Intake

**Input**: Design documents from `specs/001-conversational-intake/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Organization**: Tasks are grouped by user story so each story can be independently implemented and tested. Tests are included because the request explicitly requires TDD.

**TDD rule**: For each user story, complete its RED test tasks and verify they fail for the intended missing behavior before starting its GREEN implementation tasks. Phase 2 foundational safety tests and implementations must complete before any extraction logic.

## Phase 1: Setup

**Purpose**: Establish the backend, frontend, test runners, and CI project layout specified in `plan.md`.

- [x] T001 Create the backend package, test directories, and `backend/pyproject.toml` for Python 3.12+ managed by uv, with FastAPI, LangGraph, Pydantic, PostgreSQL driver, PyPDF2, python-docx, python-pptx, pytest, and test dependencies declared.
- [x] T002 Create the React 19, TypeScript, Vite 6, and Tailwind CSS application skeleton in `frontend/package.json`, `frontend/vite.config.ts`, and `frontend/src/`.
- [x] T003 Add PostgreSQL-only local development services and non-secret settings placeholders in `compose.yaml` and `.env.example`; exclude secrets and source-content logging.
- [x] T004 Configure backend lint/type-check/test commands in `backend/pyproject.toml` and frontend lint/type-check/test commands in `frontend/package.json`.
- [x] T005 Add `.github/workflows/ci.yml` with backend and frontend jobs, blocking merge on failed checks; reserve a required golden-evaluation job to be wired to the Phase 2 harness.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement and validate shared schema, safety, memory-only ingestion boundaries, pacing primitives, authentication/logging, and evaluation infrastructure before any user-story extraction work.

**⚠️ CRITICAL**: No user-story implementation or AI extraction logic begins until the NoFacts gate and foundational schema invariants pass.

- [x] T006 [P] Add failing unit tests in `backend/tests/unit/safety/test_no_facts.py` for candidate-AST traversal and regex rejection of digit numerals, percentages, currency/costs, date forms, and word-form quantities including “ninety percent” and “over fifteen hours”; assert the entire containing candidate is dropped.
- [x] T007 Implement deterministic candidate-tree traversal and NoFacts regex checks in `backend/src/aimplify_intake/safety/no_facts.py`; return only a pass/drop decision and never return or log rejected candidate text.
- [x] T008 [P] Add failing schema contract tests in `backend/tests/contract/test_canonical_schema.py` asserting “exactly 27 unique active field keys,” “exactly 6 active section keys,” “exactly 18 mandatory fields (15 AI-extractable and 3 declaration-only),” “exactly 9 optional fields,” and non-AI-writability for the three declaration fields plus `reviewer_notes`.
- [x] T009 Copy the authoritative 27-field inventory in `specs/001-conversational-intake/data-model.md` into `backend/src/aimplify_intake/schema/canonical_schema.json`, preserving every field key, display name, type, enum member, section, mandatory flag, fill mode, and declaration-only flag exactly; do not add a schema-discovery or schema-owner blocking step.
- [x] T010 Implement immutable schema loading and publication-time count/uniqueness checks in `backend/src/aimplify_intake/schema/registry.py`; reject activation unless it satisfies exactly 27 fields, 6 sections, 18 mandatory fields (15 AI-extractable plus 3 declaration-only), 9 optional fields, and the T008 non-AI-writability assertions.
- [x] T011 [P] Add failing RAM-only ingestion contract tests in `backend/tests/contract/ingestion/test_ram_only.py` for PDF, DOCX, PPTX, WAV, MP3, and WebM; assert the API consumes `Request.stream()` directly into `io.BytesIO`, every parser/transcriber receives that in-memory stream, and an OS-level filesystem write trap fails on any attempted temp-file/source/derived-byte write and records zero write attempts for each format.
- [x] T012 [P] Add failing pacing unit tests in `backend/tests/unit/graph/test_pacing.py` for multiple missing mandatory fields, all mandatory fields complete, optional fields left empty, and successive employee answers; assert zero questions when all mandatory fields are complete and exactly one approved question for one missing mandatory field otherwise, with no clarification prompted solely by an empty optional field.
- [x] T013 [P] Add failing security contract and CI configuration tests in `backend/tests/contract/test_security_logging.py` and `backend/tests/contract/test_cloud_identity_ci.py`; assert PII/token canaries never appear in application logs, protected session access requires OIDC, AWS/GCP/Azure long-lived credentials are absent, OIDC Workload Identity Federation trust is configured and validated, and the required CI workflow executes the cloud-identity checker.
- [x] T014 [P] Add failing golden-evaluation harness tests in `backend/tests/unit/evaluation/test_golden_runner.py` asserting a versioned `backend/tests/golden/golden_manifest.json` requires at least 50 cases and mandatory coverage for each of the 6 canonical sections, every NoFacts category (number, date, cost, percentage, and word-form quantity), all 3 modalities (chat, document, audio), single-question pacing (Principle IV), and human-only protection for `declaration_accepted`, `submitter_signature`, and `date_of_submission` (Principle III); assert the runner and CI fail if either pacing or human-only coverage is omitted.
- [x] T015 Implement the manifest-driven golden case loader and completeness/pass-rate checks in `backend/src/aimplify_intake/evaluation/golden_runner.py`; add the versioned required-coverage manifest at `backend/tests/golden/golden_manifest.json` with required section, NoFacts-category, modality, single-question-pacing, and human-only-field-protection coverage, plus at least 50 identified deterministic case records under `backend/tests/golden/cases.jsonl`.
- [x] T016 Implement the foundational field-selection pacing helper in `backend/src/aimplify_intake/graph/pacing.py`; select one missing mandatory field in canonical order and return its single schema-approved prompt, or no question if none is missing.
- [x] T017 Implement OIDC identity validation and allowlist-only, PII-free application logging in `backend/src/aimplify_intake/api/auth.py` and `backend/src/aimplify_intake/observability/logging.py`; add `.github/scripts/check_cloud_identity.py` and a required `.github/workflows/ci.yml` security job that rejects AWS/GCP/Azure long-lived credentials and validates configured OIDC Workload Identity Federation trust; do not serialize request bodies, tokens, claims, field values, or upload metadata.
- [x] T018 Implement SQLAlchemy schema-version, section, field-definition, submission, and field-value persistence models plus Alembic setup in `backend/src/aimplify_intake/persistence/models.py` and `backend/alembic/`; enforce “at most one current value per submission and field” and reject AI-origin values for `declaration_accepted`, `submitter_signature`, `date_of_submission`, and human-entry-only `reviewer_notes`.
- [x] T019 Wire the manifest-driven golden runner as a required CI check in `.github/workflows/ci.yml`; fail if fewer than 50 cases exist, any section/NoFacts-category/modality requirement or either single-question-pacing or human-only-field-protection category in `backend/tests/golden/golden_manifest.json` is missing, any case is skipped or omitted, or the pass rate is below 100%.

**Checkpoint**: NoFacts tests pass before extraction work; schema inventory is authoritative and count-validated; memory-only and pacing contracts are in place; CI has a blocking golden gate.

---

## Phase 3: User Story 1 - Submit an idea from a document or conversation (Priority: P1) 🎯 MVP

**Goal**: Accept chat, document, and audio inputs and safely map supported information into the canonical intake schema without persisting source bytes or transcripts.

**Independent Test**: Submit a multi-page PDF and each other supported source modality; verify safe accepted field updates and prove source/derived bytes are not written to disk.

### RED: Tests for User Story 1

- [X] T020 [P] [US1] Add failing HTTP and WebSocket contract tests for session creation, chat submission, raw streamed source upload, field-state retrieval, and the documented event envelopes in `backend/tests/contract/api/test_intake_http.py`.
- [X] T021 [P] [US1] Add failing parser adapter contract tests for valid multi-page PDF, DOCX, PPTX, WAV, MP3, and WebM inputs in `backend/tests/contract/ingestion/test_supported_sources.py`; assert RAM-only input and no disk artifacts per `contracts/intake-http.md` and `contracts/websocket.md`.
- [X] T022 [P] [US1] Add failing ingestion integration tests for unsupported, corrupt, and over-limit sources in `backend/tests/integration/test_source_rejection.py`; assert generic errors, no partial field writes, and release of request buffers.
- [X] T023 [P] [US1] Add failing frontend tests for chat, file/audio source selection, streaming field updates, and generic upload errors in `frontend/src/tests/intake-flow.test.tsx`.

### GREEN: Implementation for User Story 1

- [X] T024 [US1] Implement bounded raw request-body reading into request-scoped `io.BytesIO` buffers in `backend/src/aimplify_intake/ingestion/buffers.py`; reject over-limit streams and release buffers on success, failure, timeout, or disconnect.
- [X] T025 [P] [US1] Implement PDF, DOCX, and PPTX text extraction adapters using in-memory streams in `backend/src/aimplify_intake/ingestion/documents.py`; do not invoke path-based parser APIs or write derived text to disk.
- [X] T026 [P] [US1] Implement WAV, MP3, and WebM transcription adapters accepting `io.BytesIO` in `backend/src/aimplify_intake/ingestion/audio.py`; require approved no-retention provider configuration and release audio/transcript buffers after processing.
- [X] T027 [US1] Implement candidate extraction orchestration and canonical field/type validation in `backend/src/aimplify_intake/services/extraction.py`; invoke `safety/no_facts.py` on each candidate before any state update, database write, or client event.
- [X] T028 [US1] Implement atomic persistence of accepted field values and submission state in `backend/src/aimplify_intake/persistence/repositories.py`; persist no uploads, derived bytes, raw messages, or transcripts.
- [X] T029 [US1] Implement session creation, chat, source-upload, and field-state HTTP endpoints from `specs/001-conversational-intake/contracts/intake-http.md` in `backend/src/aimplify_intake/api/app.py`; use raw streamed uploads rather than multipart upload spooling.
- [X] T030 [US1] Implement authenticated WebSocket connection and `client.message`, `client.source.begin`, binary source, `client.source.commit`, and safe server events in `backend/src/aimplify_intake/api/app.py` according to `specs/001-conversational-intake/contracts/websocket.md`.
- [X] T031 [US1] Implement the responsive intake chat, source picker, safe field-state view, and WebSocket/HTTP fallback client in `frontend/src/components/IntakeChat.tsx`, `frontend/src/components/SourcePicker.tsx`, and `frontend/src/services/intake.ts`.

**Checkpoint**: User Story 1 works independently for all six file types and chat, with RAM-only parsing and safe accepted values.

---

## Phase 4: User Story 2 - Keep unverified claims out of the submission (Priority: P1)

**Goal**: Ensure unverified quantities never enter stored field values or client-visible extracted facts.

**Independent Test**: Submit adversarial values containing numerals, percentages, costs, dates, and word-form quantities; verify none appear in persisted values or client events.

### RED: Tests for User Story 2

- [X] T032 [P] [US2] Add failing integration tests sending each NoFacts adversarial category through chat, document extraction, audio transcription, HTTP, and WebSocket paths in `backend/tests/integration/test_no_facts_boundaries.py`; assert rejected candidates are absent from persistence and events.
- [X] T033 [P] [US2] Add failing property-based tests for nested candidate values and normalized punctuation/currency/date forms in `backend/tests/unit/safety/test_no_facts_properties.py`; assert deterministic whole-candidate drop behavior.

### GREEN: Implementation for User Story 2

- [X] T034 [US2] Integrate the foundational NoFacts decision into every extraction result path in `backend/src/aimplify_intake/services/extraction.py`; ensure state is mutated only with passed candidates and drop outcomes reveal no rejected value.
- [X] T035 [US2] Add a persistence-boundary guard that rejects any AI candidate not marked as NoFacts-validated in `backend/src/aimplify_intake/persistence/repositories.py`; ensure client serializers in `backend/src/aimplify_intake/api/serializers.py` receive only committed safe values.

**Checkpoint**: All evaluated unverified quantity forms are dropped consistently across every supported input and output path.

---

## Phase 5: User Story 3 - Complete missing mandatory information one question at a time (Priority: P1)

**Goal**: Ask one approved question per successful turn for one unfilled mandatory field, and none when all mandatory fields are complete.

**Independent Test**: Submit a record missing multiple required fields, verify one question, answer it, and verify the next turn asks one question for a remaining field; verify no question when all 18 are filled.

### RED: Tests for User Story 3

- [X] T036 [P] [US3] Add failing LangGraph integration tests in `backend/tests/integration/graph/test_single_question_turn.py` for multiple missing fields, one answer followed by another missing field, all fields complete, and retry/resume; assert exactly zero or one approved question per turn.
- [X] T037 [P] [US3] Add failing HTTP/WebSocket contract tests in `backend/tests/contract/api/test_clarification_contract.py` asserting the HTTP `clarification` member is one object or `null` and each WebSocket turn emits no more than one `server.clarification` event.
- [X] T038 [P] [US3] Add failing frontend pacing tests in `frontend/src/tests/clarification.test.tsx` asserting one prompt is rendered per turn and no second prompt is bundled into field updates or status messages.

### GREEN: Implementation for User Story 3

- [X] T039 [US3] Implement the LangGraph intake state, extraction-to-validation edges, and single clarification route in `backend/src/aimplify_intake/graph/intake_graph.py`; call `graph/pacing.py` once per turn and keep the question as one scalar output.
- [X] T040 [US3] Integrate clarification results and event ordering in `backend/src/aimplify_intake/api/app.py`; emit exactly one approved prompt when any mandatory field is missing and omit it when none are missing.
- [X] T041 [US3] Render the single clarification prompt and submit its answer as the next conversational turn in `frontend/src/components/ClarificationPrompt.tsx` and `frontend/src/components/IntakeChat.tsx`.

**Checkpoint**: The same single-question invariant holds at graph, HTTP, WebSocket, and UI boundaries.

---

## Phase 6: User Story 4 - Keep declarations under human control (Priority: P1)

**Goal**: Reserve Declaration Accepted, Submitter Signature, and Date of Submission for explicit human entry; prevent AI endpoint suggestions and mutations.

**Independent Test**: Ask AI to fill each human-only field through chat and source inputs, then attempt an AI-origin write; verify no suggestion or persisted AI value exists and human entry remains available.

### RED: Tests for User Story 4

- [X] T042 [P] [US4] Add failing contract tests for attempts to set or suggest `declaration_accepted`, `submitter_signature`, `date_of_submission`, and human-entry-only `reviewer_notes` through chat, extraction, HTTP, and WebSocket in `backend/tests/contract/api/test_human_only_fields.py`; assert these fields are omitted from AI updates and remain unset.
- [X] T043 [P] [US4] Add failing database constraint tests for AI-origin writes to `declaration_accepted`, `submitter_signature`, `date_of_submission`, and human-entry-only `reviewer_notes`, plus valid human-origin writes, in `backend/tests/integration/persistence/test_human_only_fields.py`.
- [X] T044 [P] [US4] Add failing frontend tests in `frontend/src/tests/human_declarations.test.tsx` asserting AI responses cannot populate declaration controls and only explicit human input updates them.

### GREEN: Implementation for User Story 4

- [X] T045 [US4] Enforce `declaration_only => ai_writable = false` for `declaration_accepted`, `submitter_signature`, and `date_of_submission`, and `fill_mode = "Human only" => ai_writable = false` for `reviewer_notes`, in extraction validation, response serialization, and persistence in `backend/src/aimplify_intake/schema/validation.py` and `backend/src/aimplify_intake/persistence/repositories.py`.
- [X] T046 [US4] Add authenticated human-controlled update endpoints for the three declarations and `reviewer_notes`, with contracts in `backend/src/aimplify_intake/api/http.py` and `specs/001-conversational-intake/contracts/intake-http.md`; accept only explicit human-origin values and never route these values through AI extraction.
- [X] T047 [US4] Implement separate human-operated declaration controls and the human-entry-only `reviewer_notes` control in `frontend/src/components/HumanDeclarations.tsx`; exclude all four non-AI-writable fields from AI-rendered state and submit values only through human-controlled inputs.

**Checkpoint**: All three human-only fields reject AI writes/suggestions and remain available for explicit human completion.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the full system against the constitution, all contracts, and the local validation guide.

- [ ] T048 [P] Add end-to-end canary tests ensuring PII, tokens, filenames, source text, and field values never appear in application, proxy, or WebSocket logs in `backend/tests/integration/test_pii_log_exclusion.py`.
- [ ] T049 [P] Add an automated ingress-to-parser contract test in `backend/tests/contract/ingestion/test_ingress_no_disk.py` that proves `Request.stream()` feeds `io.BytesIO` directly for PDF, DOCX, PPTX, WAV, MP3, and WebM, runs the API plus ingress in an OS-level filesystem sandbox/write trap, and fails on any attempted temp-file spool or source/derived-byte write; document the required no-buffer deployment settings and release gate in `deploy/ingress/README.md`.
- [X] T050 [P] Add schema-golden tests validating the inventory has 27 fields, 6 sections, 18 mandatory fields (15 AI-extractable and 3 declaration-only), and 9 optional fields in `backend/tests/contract/test_schema_golden.py`; compare every field key, type, enum member, section, fill mode, and mandatory flag with `specs/001-conversational-intake/data-model.md` and fail on unapproved drift.
- [X] T051 Run backend tests, frontend tests, all 50+ golden cases, and the end-to-end scenarios in `specs/001-conversational-intake/quickstart.md`; fix failures in the relevant source/tests before marking this task complete.
- [ ] T052 Update `specs/001-conversational-intake/quickstart.md` and `specs/001-conversational-intake/plan.md` with final runnable commands, configured upload limits, retention policy, and verified ingress behavior before release.

**Phase 7 verification note**: T048, T049, and T052 remain open because this
repository has no production reverse proxy and the accepted-data retention
policy is not approved. Application/WebSocket canaries and the API-to-parser
stream/write-trap contract pass, but proxy logs, no-buffer behavior, and
OS-level ingress writes remain deployment release gates. The 50 golden records
contain deterministic claim inputs and expected outcomes and execute chat,
document, and audio API paths with injected test providers. They validate intake
behavior without calling an external model or production provider.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: No dependencies; establishes both project toolchains.
- **Foundational (Phase 2)**: Depends on Setup. The NoFacts tests and gate (T006-T007) precede all extraction logic. The canonical inventory is already authoritative in `data-model.md`; T009 copies it directly before T010 validates and activates it.
- **User stories (Phases 3-6)**: Depend on foundational services and active canonical schema. Within each story, all RED tasks must fail for the intended missing behavior before any GREEN task begins.
- **Polish (Phase 7)**: Depends on all four user stories; the release verification also requires all 50+ golden cases to pass.

### User-story dependency graph

```text
Phase 1 Setup
    ↓
Phase 2 Foundational (NoFacts + schema + RAM/pacing/auth + golden gate)
    ├── US1 (source/chat intake MVP) ──┬── US2 (NoFacts end-to-end integration)
    │                                  ├── US3 (graph clarification)
    └──────────────────────────────────┴── US4 (human-only declarations)
US3 and US4 require US1's persisted session/field state before their end-to-end checkpoint.
Phase 7 Polish requires US1, US2, US3, and US4.
```

US2 can be implemented alongside US1 after Phase 2 because its integration tests
exercise the shared extraction boundary. US3 and US4 can begin their RED tests
after Phase 2, but their endpoint/UI integration tasks depend on US1 session
state and API surfaces.

### Parallel execution opportunities

- Setup: T001-T004 touch separate project/config files and may run in parallel; T005 follows the test command setup.
- Foundational RED tests T006, T008, T011-T014 target separate test files and may be authored in parallel; T007 follows T006. T009 copies the supplied inventory before T010 and T018 publish/use the schema.
- US1 RED tasks T020-T023 target separate contract/integration/frontend test files and may run in parallel; GREEN parser adapters T025-T026 can run in parallel after T024.
- US2 RED tasks T032-T033 can run in parallel; T034 must precede T035.
- US3 RED tasks T036-T038 can run in parallel; T039 precedes T040-T041.
- US4 RED tasks T042-T044 can run in parallel; T045 precedes T046-T047.
- Polish tests T048-T050 target separate files and can run in parallel once all stories are integrated.

### Parallel example: User Story 1

```text
RED (parallel):
  T020 HTTP/WebSocket contract tests in backend/tests/contract/api/
  T021 six-format RAM ingestion tests in backend/tests/contract/ingestion/
  T022 malformed/unsupported/oversized source tests in backend/tests/integration/
  T023 chat/source picker UI tests in frontend/src/tests/

GREEN (after RED failures are confirmed):
  T024 bounded BytesIO buffers
  T025 document parser adapters ── parallel with T026 audio adapters
  T027 safe extraction ── T028 accepted-value persistence
  T029 HTTP fallback and T030 WebSocket server
  T031 frontend intake flow
```

## Implementation Strategy

### MVP first

1. Complete Phase 1 setup.
2. Complete Phase 2, including the NoFacts gate, schema inventory validation, RAM-only ingestion contracts, pacing primitive tests, and blocking golden CI harness.
3. Complete Phase 3 (US1) for chat and all six supported file types, using safe accepted fields and no file persistence.
4. Run US1 independent tests and the quickstart PDF/no-disk validation before expanding scope.

### Incremental delivery

1. Add US2 end-to-end safety integration; demonstrate no unsafe candidate reaches storage or UI.
2. Add US3 LangGraph pacing and prove one approved question per turn.
3. Add US4 human-only declaration flow and database/API denial of AI mutations.
4. Complete Phase 7 cross-cutting privacy, ingress, schema-golden, and full CI validation.

## Notes

- Every task uses the required `- [ ] Tnnn [P?] [USn?] action + exact path` checklist format.
- `[P]` appears only where file ownership and dependencies permit parallel work.
- The application implementation and automated test suites are present. T009 uses the concrete authoritative inventory in `specs/001-conversational-intake/data-model.md`; no placeholder field names or mandatory flags may be shipped as canonical values.
- The RED tasks established automated tests before the corresponding implementation work.

## Phase 8: Convergence

- [X] T053 Replace metadata-only golden pass bookkeeping with executable deterministic cases and expected outcomes across the buildable intake paths; fail on behavioral mismatches, missing cases, or unmet safety, pacing, human-only, and modality coverage per SC-002, SC-003, SC-004, SC-005, and SC-006 (partial)

## Phase 9: Convergence

- [X] T054 Update the quickstart, plan, and Phase 7 verification note to describe the executable deterministic golden API cases and stubbed providers accurately, and remove obsolete claims that the suite is metadata-only or the application structure is not implemented per SC-006 (partial)

## Phase 10: Convergence

- [X] T055 Run the frontend tests, typecheck, and production build with dependencies from `frontend/package-lock.json`; fix failures affecting intake, clarification pacing, or human declarations per T051 and SC-007 (partial)
