<!--
Sync Impact Report
Version change: unversioned scaffold -> 1.0.0
Modified principles: None; this is the initial ratification of the project principles.
Added sections: Six Core Principles; Additional Constraints; Development Workflow.
Removed sections: None.
Follow-up TODOs: None.
-->

# AIMPLIFY Conversational Intake Bot Constitution

## Core Principles

### I. Deterministic Safety Gate - NoFacts Pattern
Every candidate value produced by AI extraction MUST pass through a deterministic NoFacts
safety gate before it is persisted or displayed. The gate MUST silently drop any value that
contains unverified numbers, percentages, costs, dates, or word-form quantities, including
expressions such as "ninety percent" or "over fifteen hours." This prevents unverified facts
from entering the intake record or being presented as established information.

### II. Zero-Disk Ephemeral Ingestion
Uploaded PDF, DOCX, and PPTX documents and WAV, MP3, and WebM audio recordings MUST be
ingested and processed in RAM only, using `io.BytesIO`. The system MUST NOT persist any
uploaded or derived file bytes to disk. This minimizes retention of sensitive intake material.

### III. Canonical Schema and Human-Only Boundaries
The intake MUST use the canonical 27-field schema across exactly 6 sections, and MUST
validate exactly 18 mandatory fields. The Declaration Accepted, Date of Submission, and
Submitter Signature fields are human-only: AI MUST NOT pre-fill or suggest values for them.
This keeps the intake contract consistent and reserves declarations for the responsible
human submitter.

### IV. One Clarification Question per Turn
The conversational intake engine MUST ask no more than one clarification question in each
turn. It MUST NOT combine multiple questions into a compound question. This keeps each
interaction focused and lets the submitter respond unambiguously.

### V. Zero-Trust Security and PII Protection
Application logs MUST contain no personally identifiable information (PII). Cloud access
MUST use OIDC federated identity, and MUST NOT rely on static cloud secrets. These controls
limit sensitive-data exposure and reduce the risk of long-lived credentials.

### VI. CI Golden Evaluation Gate
The CI golden evaluation suite MUST contain at least 50 cases, and 100% of its cases MUST
pass with zero gaps before any pull request can be merged. This makes the required behavior
an enforced merge gate rather than a discretionary review check.

## Additional Constraints

The schema, safety, ingestion, privacy, and interaction requirements in this constitution
apply to all intake paths and all candidate values, regardless of which model, integration,
or interface produces them. Any change to the canonical field count, section count, mandatory
field count, or human-only fields requires a constitutional amendment before implementation.

## Development Workflow

Changes MUST include automated checks for the constitutional requirements they affect.
Changes to extraction, schema validation, or conversation behavior MUST be covered by the
golden evaluation suite. CI MUST report the complete suite result and block merging on any
failure or omitted case. Pull request review MUST verify that changes preserve compliance
with every applicable principle.

## Governance

This constitution governs project decisions and supersedes conflicting local practices.
Amendments require a documented proposal, review and approval by the project maintainers,
and an update to this file. Implementations and pull requests MUST demonstrate compliance
with applicable principles; a deviation requires an explicit constitutional amendment rather
than an undocumented exception.

The constitution uses semantic versioning. A MAJOR increment is required for a backward-
incompatible change to a principle; a MINOR increment is required when adding or materially
expanding a principle or governance section; a PATCH increment is required for clarifications
and non-semantic wording changes. The Sync Impact Report at the top of this file is temporary
review material and MUST be removed before the amended file is committed.

**Version**: 1.0.0 | **Ratified**: 2026-11-03 | **Last Amended**: 2026-11-03
