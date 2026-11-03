# Data Model: AIMPLIFY Conversational Idea Intake

## Canonical schema contract

The authoritative AIMPLIFY inventory is recorded below: **27 fields across
exactly 6 sections**, with **exactly 18 mandatory fields total**: 15
AI-extractable fields and 3 human-only declaration fields. The inventory has
exactly 9 optional fields. The optional `reviewer_notes` field is
human-entry-only; it is not one of the three mandatory declaration fields.

### Sections

| Section key | Canonical section name |
|---|---|
| `section_01` | Submitter Information |
| `section_02` | Idea Details |
| `section_03` | Impact and Feasibility |
| `section_04` | Program and Hackathon Alignment |
| `section_05` | Supporting Materials and Notes |
| `section_06` | Declaration (Human Only) |

### Field registry slots

Each row is one registry entry. `AI writable = No` means the AI cannot set,
suggest, or mutate the value. `Declaration-only = Yes` marks the three mandatory
fields that are strictly reserved for the human submitter. Enum values and
fill-mode labels are canonical. Optional fields, including those with fill mode
`Ask`, do not trigger mandatory-field clarification or block submission; an
employee may provide them voluntarily.

| Key | Canonical field name | Section | Type / allowed values | Mandatory | Fill mode | AI writable | Declaration-only |
|---|---|---|---|---:|---|---:|---:|
| `submitter_name` | Full Name | `section_01` | string | Yes | Auto/Extract | Yes | No |
| `submitter_email` | Work Email | `section_01` | email | Yes | Auto/Extract | Yes | No |
| `business_unit` | Business Unit / Department | `section_01` | string | Yes | Auto/Extract | Yes | No |
| `designation` | Designation / Role | `section_01` | string | Yes | Auto/Extract | Yes | No |
| `reporting_manager` | Reporting Manager | `section_01` | string | Yes | Auto/Extract | Yes | No |
| `manager_email` | Manager Email | `section_01` | email | No | Auto/Extract | Yes | No |
| `idea_title` | Idea Title | `section_02` | string | Yes | Suggest/Extract | Yes | No |
| `idea_category` | Idea Category | `section_02` | enum: AI Agent; Process Automation; Data & Analytics; AI-SDLC Tool; Client Solution; Internal Tool; L&D / Training; Governance & Compliance; Platform / Infrastructure; Other | Yes | Suggest/Extract | Yes | No |
| `aimplify_platform` | AIMPLIFY Platform | `section_02` | enum: Forge; Atlas; Sentinel; Titan | Yes | Suggest/Extract | Yes | No |
| `idea_maturity` | Idea Maturity | `section_02` | enum: Idea; Prototype; PoC; MVP | Yes | Suggest/Extract | Yes | No |
| `problem_statement` | Problem Statement | `section_02` | text | Yes | Draft + Coach | Yes | No |
| `proposed_solution` | Proposed Solution | `section_02` | text | Yes | Draft + Coach | Yes | No |
| `expected_benefits` | Expected Benefits / Business Value | `section_03` | text | Yes | Draft + Coach | Yes | No |
| `target_beneficiaries` | Who Benefits? | `section_03` | string | Yes | Suggest/Extract | Yes | No |
| `estimated_users` | Estimated Users / Scale | `section_03` | string | No | Ask | Yes | No |
| `estimated_effort` | Estimated Effort to Build | `section_03` | enum: Small; Medium; Large; XL; Not Sure | Yes | Suggest/Extract | Yes | No |
| `priority_level` | Priority Level | `section_03` | enum: High; Medium; Low; Exploratory | No | Ask | Yes | No |
| `preferred_technology` | Preferred Technology / Tools | `section_03` | string | No | Suggest/Extract | Yes | No |
| `submission_type` | Submission Type | `section_04` | enum: General Idea; Hackathon Entry; AIIM Cohort Project; AI CIC Initiative; Client Solution Idea; Internal Tool Request | Yes | Suggest/Extract | Yes | No |
| `related_event` | Related Hackathon / Event | `section_04` | string | No | Ask | Yes | No |
| `build_intent` | Build Intent (Self / Team) | `section_04` | enum: Lead myself; Need team members; Submitting idea only; Join existing team | No | Ask | Yes | No |
| `team_members` | Team Members | `section_04` | string | No | Ask | Yes | No |
| `reference_links` | Reference Links | `section_05` | string | No | Suggest/Extract | Yes | No |
| `reviewer_notes` | Additional Notes for Reviewer | `section_05` | text | No | Human only | No | No |
| `declaration_accepted` | Declaration Accepted | `section_06` | boolean | Yes | Human only | **No** | **Yes** |
| `submitter_signature` | Submitter Signature | `section_06` | string | Yes | Human only | **No** | **Yes** |
| `date_of_submission` | Date of Submission | `section_06` | date | Yes | Human only | **No** | **Yes** |

Registry invariants: 27 unique fields; 6 sections; exactly 18 mandatory fields
(15 AI-extractable and 3 declaration-only); exactly 9 optional fields.
`reviewer_notes` is human-entry-only and cannot be AI-written. Field keys remain
stable across schema versions; names, types, enum values, mandatory flags,
section assignments, and fill modes are versioned metadata. Every submission
references the schema version used at creation.

## Entities

### `SchemaVersion`

Immutable version of the active canonical intake schema.

| Attribute | Meaning | Validation |
|---|---|---|
| `schema_version` | Stable version identifier | Required; unique |
| `published_at` | Time the registry version was published | Required |
| `field_count` | Registered canonical field count | Exactly 27 |
| `section_count` | Registered section count | Exactly 6 |
| `mandatory_count` | Total mandatory field count | Exactly 18: 15 AI-extractable and 3 declaration-only |

### `IntakeSection`

One of six ordered sections in a schema version. Contains a stable key, display
name, and ordinal. Exactly six sections must exist in each published version.

### `CanonicalFieldDefinition`

One canonical field within a section. Contains stable field key, display name,
description, value type, section key, ordinal, `mandatory`, `fill_mode`,
`ai_writable`, and `declaration_only` flags. Enforce
`fill_mode = "Human only" => ai_writable = false`; exactly the three Declaration
fields have `declaration_only = true`. `reviewer_notes` is also non-AI-writable
but is optional and is not a declaration field. Each mandatory field has one
approved, single-question `clarification_prompt`; this is field metadata, not an
additional canonical field.

### `IdeaSubmission`

An employee's idea intake, referencing a schema version. Contains an opaque
submission identifier, authorized submitter subject reference, lifecycle status
(`in_progress`, `ready_for_human_declaration`, `submitted`), and created/updated
timestamps. The subject reference is access-controlled and MUST NOT be written
to logs. Do not store raw source content here.

### `FieldValue`

Accepted value for one field in one submission. Contains submission ID, field
key, typed value, origin (`ai_extracted` or `human_entered`), and update time.
There can be at most one current value per submission and field. Raw source
quotes, full chat turns, and audio transcriptions are not persisted. A candidate
must pass field validation and the NoFacts gate before becoming a `FieldValue`.
Fields with `fill_mode = "Human only"` accept `human_entered` values only.

### `IntakeSource` (transient)

Request-scoped source descriptor with modality (`chat`, `pdf`, `docx`, `pptx`,
`wav`, `mp3`, or `webm`), content type, declared length, and in-memory buffer.
It is not a persistent database entity. On success, error, disconnect, or timeout,
release the buffer and transient extracted text.

### `ClarificationTurn` (transient)

One graph turn with the missing mandatory field key and either zero questions
(when no mandatory fields are missing) or exactly one question string. Question
text is not stored as a list and is not appended with a reducer.

## Relationships and lifecycle

- One `SchemaVersion` has exactly six `IntakeSection` records and 27
  `CanonicalFieldDefinition` records.
- One `IntakeSection` contains one or more canonical fields; all six sections
  must be represented.
- One `IdeaSubmission` references one immutable schema version and has zero or
  more `FieldValue` records.
- Each `FieldValue` references exactly one field definition in the submission's
  schema version.
- Candidate values transition through `extracted -> validated -> accepted` or
  `extracted -> dropped`. Only `accepted` values may be persisted or displayed.
- Submission transitions: `in_progress -> ready_for_human_declaration ->
  submitted`. AI cannot perform the human declaration transition or set the
  three declaration-only values.

## Validation and integrity rules

1. Publishing a schema version fails unless it has exactly 27 unique fields,
   exactly 6 sections, exactly 18 mandatory fields (15 AI-extractable and 3
   declaration-only), and exactly 9 optional fields.
2. `declaration_accepted`, `submitter_signature`, and `date_of_submission` exist
   exactly once each, are mandatory, and have `declaration_only = true` and
   `ai_writable = false`. `reviewer_notes` is optional, has
   `fill_mode = "Human only"`, and `ai_writable = false`. Database constraints
   and service-boundary checks reject AI-origin values for all four non-AI-writable
   keys.
3. Field keys submitted by clients must belong to the submission's schema version.
4. Required values are validated against the canonical type and field-specific
   constraints; unknown constraints must be copied from the source schema, not
   invented.
5. The deterministic NoFacts gate runs on every AI candidate before persistence
   and before any response or event containing that value. It traverses the
   structured candidate value tree and applies regex recognizers to text leaves.
   The policy is fail-closed: candidate values containing unverified numbers,
   percentages, costs, dates, or word-form quantities are silently dropped
   before persistence or display, even if those quantities appear in
   user-provided messages, documents, or audio transcriptions. User source text
   is not an independent verification source.
6. Human-entered `reviewer_notes` and declarations bypass AI suggestion paths
   but still receive ordinary type and authorization validation. Declaration
   submission also requires explicit human confirmation.
7. Raw uploads, derived file bytes, transcripts, and unfiltered conversation
   messages are never database values. Text extraction and transcription buffers
   are ephemeral.
8. Database logs, telemetry, and error messages exclude PII and field/source
   values. Database encryption and access controls protect accepted submission
   values at rest.
9. A transaction writes accepted field changes atomically; emitted client updates
   represent committed safe values only.

## Schema activation

The concrete field inventory and enum choices in this document are the
authoritative source for `canonical_schema.json`, registry seed data, and
migrations. Automated schema tests MUST verify all names, types, section
assignments, fill modes, mandatory flags, enum members, and count invariants
against this inventory.
