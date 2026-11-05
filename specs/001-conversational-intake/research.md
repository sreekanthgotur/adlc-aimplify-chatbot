# Research: AIMPLIFY Conversational Idea Intake

**Date**: 2026-11-03  
**Scope**: Resolve design choices required by the approved feature specification and requested stack.

## Decisions

### Upload and parsing boundary

- **Decision**: Consume source uploads as bounded raw request streams and copy
  chunks into request-scoped `io.BytesIO` buffers. Do not use FastAPI/Starlette's
  default multipart `UploadFile` path, since it may spool to temporary storage.
  Configure ingress, proxies, parsers, and deployment diagnostics to avoid disk
  buffering or source-content dumps.
- **Rationale**: The no-disk invariant applies to the complete ingestion path, not
  merely to the document parser. A strict memory-only promise needs limits on
  bytes and concurrent in-flight uploads, plus verification of every intermediary.
- **Alternatives considered**: Default multipart parsing was rejected because
  uploaded files may use spooled temporary files. Loading an unrestricted body in
  one operation was rejected because it permits unbounded memory consumption.
- **References**: [Starlette request streaming and files](https://www.starlette.io/requests/),
  [FastAPI request files](https://fastapi.tiangolo.com/tutorial/request-files/),
  [Python temporary files](https://docs.python.org/3/library/tempfile.html#tempfile.SpooledTemporaryFile).

### WebSocket authentication and event validation

- **Decision**: Authenticate the browser's WebSocket handshake using the existing
  secure, same-site OIDC session cookie; validate `Origin` against an allowlist
  before accepting. Validate each message envelope, payload size, authorization,
  and rate. Do not place bearer tokens in query strings or log frames.
- **Rationale**: Browser WebSocket APIs do not expose arbitrary handshake headers
  consistently; the cookie is already available to the same-origin handshake.
  Origin checking and per-message authorization mitigate cross-site and
  unauthorized use.
- **Alternatives considered**: Query-string tokens were rejected because URLs can
  be captured in access logs. Accepting first and authorizing later was rejected
  because it risks sending protected data before identity is established.
- **References**: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/),
  [Starlette WebSockets](https://www.starlette.io/websockets/),
  [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).

### Single-question orchestration

- **Decision**: A dedicated LangGraph clarification node deterministically selects
  one missing mandatory field and emits its one approved, field-specific prompt
  as a scalar `question`. Conditional routing selects either that node or the
  completion path. Do not have the model author free-form clarification prose;
  never use parallel question-producing nodes or an append reducer.
- **Rationale**: The output shape and graph topology make one-question pacing an
  enforceable application invariant rather than a prompt-only expectation. A
  reviewed prompt per canonical field avoids the ambiguity of trying to detect
  compound natural-language questions after generation.
- **Alternatives considered**: Unrestricted natural-language clarification was
  rejected because punctuation or prompt instructions cannot guarantee one
  semantic question. A list of questions was rejected because it allows bundling.
- **References**: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
  [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts),
  [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output).

### Deterministic NoFacts implementation

- **Decision**: Normalize each structured candidate and traverse its value tree
  (the candidate AST) with deterministic validators. Apply regex recognizers to
  every text leaf for digit numerals, percentages, currency/costs, date forms,
  and word-form quantities. Drop the whole candidate if a forbidden unverified
  quantity is present; never ask an LLM to approve its own candidate.
- **Rationale**: Structural traversal ensures nested candidate values do not
  bypass the same policy; pattern recognizers cover the stated numeric forms.
- **Alternatives considered**: Filtering only the rendered display string was
  rejected because structured/nested values could bypass it. LLM-based review
  was rejected as non-deterministic.

### NoFacts gate semantics

- **Decision**: Implement NoFacts as deterministic ordinary service code after
  extraction and before state mutation, persistence, or display. With no trusted
  numeric verification source specified, fail closed: drop any AI candidate
  containing an unverified number, percentage, cost, date, or word-form quantity.
  Do not treat the fact that a claim appeared in user-provided text as independent
  verification.
- **Rationale**: Regex/date/currency/word-quantity detection can be deterministic;
  it cannot establish that an adversarial claim is true. Failing closed respects
  the constitution without inventing a verification service.
- **Alternatives considered**: Allowing quantities merely because they occur in
  the source was rejected because user-provided source text can itself contain
  adversarial, unverified claims. Delegating the decision to the LLM was rejected
  because it would no longer be deterministic.
- **References**: [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/),
  [LangGraph state and nodes](https://docs.langchain.com/oss/python/langgraph/graph-api).
- **Constraint**: If product owners later want supported numerical claims, they
  must define a trusted verification source and amend the gate policy before
  implementation; no such source is assumed in this design.

### PII protection and OIDC

- **Decision**: Log only allowlisted event names, outcome codes, and random
  correlation identifiers. Exclude tokens, claims, employee identifiers, source
  text, field values, transcripts, filenames, and WebSocket payloads. Validate
  OIDC tokens according to issuer, audience, signature, expiry, and nonce/session
  requirements. Use workload identity federation for cloud resources.
- **Rationale**: Redaction after serializing arbitrary request/error objects is
  less reliable than logging an allowlist of safe fields.
- **Alternatives considered**: Logging full request or exception payloads was
  rejected because they can contain PII or credentials. Static cloud keys were
  rejected by the constitution.
- **References**: [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html),
  [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html),
  [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).

### Persistence and database

- **Decision**: Use PostgreSQL as the relational store for an immutable,
  versioned 27-field registry, submission metadata, and accepted field values.
  Persist no source files, raw messages, or transcripts.
- **Rationale**: Relational constraints and transactions fit the fixed canonical
  schema and provide atomic validation/persistence of safe values.
- **Alternatives considered**: Storing all state in a schemaless JSON document
  was rejected because it weakens enforcement of exact field, mandatory, and
  human-only invariants. No in-memory-only database was selected because
  submissions must survive process restarts.
- **Assumption**: PostgreSQL is selected as the database because the request asks
  for a database schema but does not name a database engine.

### Canonical schema inventory

- **Decision**: Use the concrete field keys, names, types, enum values, section
  assignments, and fill modes recorded in `data-model.md` as the authoritative
  schema for registry data and migrations. To satisfy the constitutional limit
  of exactly 18 mandatory fields total, `priority_level`, `preferred_technology`,
  and `build_intent` are optional; the three declaration fields remain mandatory.
- **Rationale**: The schema owner supplied the 27-field inventory. Its initial
  mandatory flags totaled 21 when the three mandatory human declarations were
  counted. The owner selected these three AI-extractable fields to become optional,
  yielding 15 mandatory AI-extractable fields plus 3 mandatory declarations.
- **Alternatives considered**: Keeping all 21 supplied mandatory flags would
  conflict with the constitution. Guessing section assignments or other field
  names was unnecessary once the authoritative inventory was supplied.

### Unspecified operational policy

- **Decision**: Use configurable request-size and concurrency limits, bounded
  processing timeouts, and a configurable retention policy for accepted
  submissions. No numeric service-level targets are prescribed by this plan.
- **Rationale**: The approved specification sets no upload cap, peak volume,
  latency objective, or retention period. These are deployment decisions rather
  than reasons to invent product acceptance targets.
- **Alternatives considered**: Hard-coding arbitrary production limits was
  rejected. The implementation must select and document values before release.
