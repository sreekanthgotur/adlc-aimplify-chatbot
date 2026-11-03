# Feature Specification: AIMPLIFY Conversational Idea Intake

**Feature Branch**: `develop`

**Created**: 2026-11-03

**Status**: Approved (Gate G1 Sign-off)

**Input**: User description: "Replace the static 27-field web form with a multi-modal conversational intake bot for employee ideas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit an idea from a document or conversation (Priority: P1)

An employee can submit an idea in chat or provide an idea document, and the bot extracts
information into the established intake schema. This replaces the static form with a more
accessible, guided submission experience.

**Why this priority**: Employees need a usable way to start and complete an idea submission.

**Independent Test**: Provide a valid multi-page PDF containing idea details and verify that
the bot extracts supported information without writing uploaded bytes to disk.

**Acceptance Scenarios**:

```gherkin
Scenario: Extract an idea from a valid multi-page PDF in memory
  Given an employee has a valid multi-page PDF containing idea information
  When the employee submits the PDF to the intake bot
  Then the bot extracts supported information from the document
  And document bytes are processed in memory only
  And no uploaded or derived document bytes are written to disk
```

```gherkin
Scenario: Start an idea submission through chat or an audio memo
  Given an employee has idea information as conversational messages or a WAV, MP3, or WebM audio memo
  When the employee submits the messages or audio memo
  Then the bot uses the messages or audio transcription as intake input
  And any audio bytes are processed in memory only
  And no uploaded or derived audio bytes are written to disk
```

```gherkin
Scenario: Extract an idea from another supported document format
  Given an employee has a valid DOCX or PPTX idea document
  When the employee submits the document to the intake bot
  Then the bot extracts supported information from the document
  And document bytes are processed in memory only
  And no uploaded or derived document bytes are written to disk
```

---

### User Story 2 - Keep unverified claims out of the submission (Priority: P1)

An employee can provide idea details without unsupported numeric claims being accepted as
facts. The deterministic safety gate prevents those claims from being persisted or displayed
as extracted field values.

**Why this priority**: Unverified quantities can mislead reviewers and compromise the trustworthiness of submissions.

**Independent Test**: Submit adversarial text with an unverified numeric claim and verify that
the claim is dropped before it is saved or displayed.

**Acceptance Scenarios**:

```gherkin
Scenario: Drop an unverified numeric claim
  Given an employee submits adversarial idea text containing unverified claims such as "ninety percent", "15%", "$200", "2026-01-02", and "over fifteen hours"
  When the bot extracts candidate field values
  Then the deterministic NoFacts gate drops each candidate value containing an unverified number, percentage, cost, date, or word-form quantity
  And none of the dropped values are persisted
  And none of the dropped values are displayed as extracted facts
```

---

### User Story 3 - Complete missing mandatory information one question at a time (Priority: P1)

When required information is missing, the employee receives one focused clarification
question per turn and can answer it before the bot asks about another missing item.

**Why this priority**: Single-question pacing makes the conversation easier to follow and answer.

**Independent Test**: Submit an idea missing multiple mandatory fields and verify that each
bot turn contains exactly one clarification question.

**Acceptance Scenarios**:

```gherkin
Scenario: Ask one clarification question when mandatory fields are missing
  Given an employee's idea submission is missing at least two mandatory fields
  When the bot responds to the submission
  Then the response contains exactly one clarification question
  And the question addresses one unfilled mandatory field
  And the bot does not combine questions about multiple fields
  When the employee answers that question and another mandatory field remains unfilled
  Then the next bot turn contains exactly one clarification question about one unfilled mandatory field
```

```gherkin
Scenario: Do not ask for clarification when all mandatory fields are filled
  Given an employee's idea submission contains values for all 18 mandatory fields
  When the bot evaluates the submission for missing mandatory information
  Then the bot does not ask a clarification question for a mandatory field
```

---

### User Story 4 - Keep declarations under human control (Priority: P1)

An employee completes the declaration, signature, and submission date personally. The bot
does not infer, suggest, or pre-fill these values.

**Why this priority**: Declarations and signatures must represent the employee's own actions and intent.

**Independent Test**: Submit content that asks the bot to complete declaration fields and
verify that those fields remain unset by the bot.

**Acceptance Scenarios**:

```gherkin
Scenario: Refuse to automate human-only declaration fields
  Given the intake includes Declaration Accepted, Date of Submission, and Submitter Signature fields
  And an employee asks the bot to fill those fields
  When the bot processes the request
  Then the bot does not pre-fill or suggest a value for any of those fields
  And the fields remain for the employee to complete
```

### Edge Cases

```gherkin
Scenario: Reject an unreadable or unsupported upload without retaining it
  Given an employee submits a corrupted document or a file in an unsupported format
  When the bot cannot read the submitted file as an accepted input
  Then the bot tells the employee that the file could not be processed
  And the bot does not extract or persist candidate values from the file
  And no uploaded file bytes are written to disk
```

```gherkin
Scenario: Preserve an idea when an optional field is empty
  Given an employee submits an idea with all mandatory fields filled and an optional field empty
  When the bot evaluates the submission
  Then the bot does not ask a mandatory-field clarification question about the optional field
  And the bot leaves the optional field empty
```

```gherkin
Scenario: Keep personal information out of logs and use federated cloud identity
  Given the bot processes an employee submission containing personally identifiable information
  When the bot records application events and accesses cloud resources
  Then application logs contain no personally identifiable information
  And cloud access uses OIDC federated identity
  And cloud access does not rely on static cloud secrets
```

```gherkin
Scenario: Block merge when golden evaluation cases fail or are omitted
  Given the CI golden evaluation suite contains at least 50 cases
  When a proposed change is evaluated for merge
  Then the change is eligible for merge only if 100% of the cases pass
  And no golden evaluation case is omitted
```

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The intake bot MUST accept idea information provided through conversational messages, PDF, DOCX, PPTX, WAV, MP3, and WebM.
- **FR-002**: The system MUST process uploaded document and audio bytes in memory only and MUST NOT write uploaded or derived file bytes to disk.
- **FR-003**: The system MUST extract supported information into the canonical 27-field intake schema across exactly 6 sections.
- **FR-004**: The system MUST identify and validate exactly 18 mandatory fields in the canonical schema.
- **FR-005**: The system MUST pass every AI-extracted candidate field value through a deterministic NoFacts gate before displaying or persisting it.
- **FR-006**: The NoFacts gate MUST silently drop any candidate value containing unverified numbers, percentages, costs, dates, or word-form quantities.
- **FR-007**: When one or more mandatory fields are unfilled, the bot MUST ask exactly one clarification question in that turn, addressing one unfilled mandatory field.
- **FR-008**: The bot MUST NOT combine multiple clarification questions in one turn.
- **FR-009**: The AI MUST NOT pre-fill or suggest values for Declaration Accepted, Date of Submission, or Submitter Signature.
- **FR-010**: Application logs MUST contain no personally identifiable information.
- **FR-011**: Cloud access MUST use OIDC federated identity and MUST NOT rely on static cloud secrets.
- **FR-012**: The CI golden evaluation suite MUST contain at least 50 cases, and all cases MUST pass without gaps before a pull request can be merged.

### Key Entities

- **Idea Submission**: An employee's proposed idea and its extracted field values across the canonical six sections.
- **Canonical Intake Field**: A field in the 27-field schema, with a defined mandatory status; three declaration fields are reserved for human completion.
- **Intake Source**: Conversational messages, a supported document, or a supported audio memo and its transcription.
- **Candidate Value**: An AI-extracted value for an intake field that must pass the NoFacts gate before display or persistence.
- **Clarification Turn**: A bot response asking one question about one unfilled mandatory field.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 27 canonical fields are represented across exactly 6 sections, and exactly 18 are identified as mandatory.
- **SC-002**: In all golden evaluation cases containing unverified numeric or quantity claims, 100% of those candidate values are absent from both persisted records and displayed extracted values.
- **SC-003**: In every evaluated turn where mandatory fields remain unfilled, the bot asks exactly one clarification question about one such field.
- **SC-004**: In all evaluation cases, AI-generated values or suggestions for the three human-only fields are zero.
- **SC-005**: In all supported document and audio ingestion evaluations, zero uploaded or derived file bytes are written to disk.
- **SC-006**: The CI golden evaluation suite contains at least 50 cases, and 100% pass with zero omitted cases before merge.
- **SC-007**: Employees can submit idea information through chat, supported documents, or supported audio memos and have supported information represented in the same canonical intake schema.

## Assumptions

- The existing canonical field definitions determine the names and meanings of all 27 fields and which 18 are mandatory; this specification does not invent or redefine them.
- "Declaration," "Signature," and "Date" refer to Declaration Accepted, Submitter Signature, and Date of Submission, respectively.
- Audio memos in WAV, MP3, and WebM are transcribed for use as intake input; the audio itself is not retained as a file.
- An unfilled optional field does not trigger a mandatory-field clarification question.
- This feature replaces the static form as the primary intake experience; employees may still complete human-only declaration fields through a human-controlled interaction.
- The CI golden suite is maintained as part of the project and is the authoritative set of evaluated cases.
- An unreadable or unsupported upload is rejected with a clear message; its file bytes are not retained.
