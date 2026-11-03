# Data Model: AIMPLIFY Conversational Idea Intake

## Canonical schema contract

The authoritative schema contains **27 fields across exactly 6 sections**, of
which **exactly 18 are mandatory**. The project source did not contain the
canonical 27 field names, types, descriptions, mandatory flags, or section
allocation when this design was prepared. This document therefore defines stable
field slots and integrity rules without fabricating the missing canonical
inventory. The authoritative intake-form inventory is a prerequisite to
production registry seed data and migrations.

### Sections

| Section key | Canonical section name |
|---|---|
| `section_01` | To be mapped from authoritative schema |
| `section_02` | To be mapped from authoritative schema |
| `section_03` | To be mapped from authoritative schema |
| `section_04` | To be mapped from authoritative schema |
| `section_05` | To be mapped from authoritative schema |
| `section_06` | To be mapped from authoritative schema |

### Field registry slots

Each row is one registry entry. `mandatory` values and section assignments must
be copied from the approved canonical schema; do not infer them from this table.
The three human-only keys are fixed by the constitution.

| Key | Canonical field name | Section | Mandatory | AI writable |
|---|---|---|---|---|
| `field_01` | To be mapped | To be mapped | To be mapped | Yes |
| `field_02` | To be mapped | To be mapped | To be mapped | Yes |
| `field_03` | To be mapped | To be mapped | To be mapped | Yes |
| `field_04` | To be mapped | To be mapped | To be mapped | Yes |
| `field_05` | To be mapped | To be mapped | To be mapped | Yes |
| `field_06` | To be mapped | To be mapped | To be mapped | Yes |
| `field_07` | To be mapped | To be mapped | To be mapped | Yes |
| `field_08` | To be mapped | To be mapped | To be mapped | Yes |
| `field_09` | To be mapped | To be mapped | To be mapped | Yes |
| `field_10` | To be mapped | To be mapped | To be mapped | Yes |
| `field_11` | To be mapped | To be mapped | To be mapped | Yes |
| `field_12` | To be mapped | To be mapped | To be mapped | Yes |
| `field_13` | To be mapped | To be mapped | To be mapped | Yes |
| `field_14` | To be mapped | To be mapped | To be mapped | Yes |
| `field_15` | To be mapped | To be mapped | To be mapped | Yes |
| `field_16` | To be mapped | To be mapped | To be mapped | Yes |
| `field_17` | To be mapped | To be mapped | To be mapped | Yes |
| `field_18` | To be mapped | To be mapped | To be mapped | Yes |
| `field_19` | To be mapped | To be mapped | To be mapped | Yes |
| `field_20` | To be mapped | To be mapped | To be mapped | Yes |
| `field_21` | To be mapped | To be mapped | To be mapped | Yes |
| `field_22` | To be mapped | To be mapped | To be mapped | Yes |
| `field_23` | To be mapped | To be mapped | To be mapped | Yes |
| `field_24` | To be mapped | To be mapped | To be mapped | Yes |
| `declaration_accepted` | Declaration Accepted | To be mapped | To be mapped | **No** |
| `submitter_signature` | Submitter Signature | To be mapped | To be mapped | **No** |
| `date_of_submission` | Date of Submission | To be mapped | To be mapped | **No** |

The registry MUST contain 27 unique active field keys, exactly 6 active section
keys, exactly 18 mandatory fields, and exactly 3 human-only fields. The field key
is stable across schema versions; display names, descriptions, types, and
section associations are versioned metadata. Every submission references the
schema version used at creation.

## Entities

### `SchemaVersion`

Immutable version of the active canonical intake schema.

| Attribute | Meaning | Validation |
|---|---|---|
| `schema_version` | Stable version identifier | Required; unique |
| `published_at` | Time the registry version was published | Required |
| `field_count` | Registered canonical field count | Exactly 27 |
| `section_count` | Registered section count | Exactly 6 |
| `mandatory_count` | Mandatory field count | Exactly 18 |

### `IntakeSection`

One of six ordered sections in a schema version. Contains a stable key, display
name, and ordinal. Exactly six sections must exist in each published version.

### `CanonicalFieldDefinition`

One canonical field within a section. Contains stable field key, display name,
description, value type, section key, ordinal, `mandatory`, `human_only`, and
`ai_writable` flags. Enforce `human_only => ai_writable = false`; at least the
three fixed declaration fields are human-only. The canonical inventory determines
whether those fields are included in the mandatory count. Each mandatory field
also has one approved, single-question `clarification_prompt`; this is field
metadata, not an additional canonical field.

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
The human-only fields accept `human_entered` values only.

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
  three human-only values.

## Validation and integrity rules

1. Publishing a schema version fails unless it has exactly 27 unique fields,
   exactly 6 sections, and exactly 18 mandatory fields.
2. The three fixed human-only field keys exist exactly once each and cannot be
   AI-writable. A database constraint or trigger and the service boundary both
   reject AI-origin values for these keys.
3. Field keys submitted by clients must belong to the submission's schema version.
4. Required values are validated against the canonical type and field-specific
   constraints; unknown constraints must be copied from the source schema, not
   invented.
5. The deterministic NoFacts gate runs on every AI candidate before persistence
   and before any response or event containing that value. It traverses the
   structured candidate value tree and applies regex recognizers to text leaves.
   Unverified number, percentage, cost, date, and word-quantity candidates are
   silently dropped.
6. Human-entered declarations bypass AI suggestion paths but still receive
   ordinary type and authorization validation.
7. Raw uploads, derived file bytes, transcripts, and unfiltered conversation
   messages are never database values. Text extraction and transcription buffers
   are ephemeral.
8. Database logs, telemetry, and error messages exclude PII and field/source
   values. Database encryption and access controls protect accepted submission
   values at rest.
9. A transaction writes accepted field changes atomically; emitted client updates
   represent committed safe values only.

## Open implementation prerequisite

Before creating production migrations or registry seed data, obtain and review the
authoritative 27-field inventory, including names, types, six-section placement,
and the exact 18 mandatory flags. This design deliberately does not assign
placeholder fields to sections or guess mandatory status.
