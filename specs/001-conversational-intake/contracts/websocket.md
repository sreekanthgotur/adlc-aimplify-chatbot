# WebSocket Contract: AIMPLIFY Intake Streaming

## Connection

- **Endpoint**: `wss://<host>/api/v1/sessions/{session_id}/stream`
- **Authentication**: Existing secure, HttpOnly, SameSite OIDC session cookie.
  The service authenticates and authorizes before accepting the socket.
- **Origin**: The handshake `Origin` MUST match the configured allowlist.
- **Subprotocol**: `aimplify.intake.v1`
- **Content types**: UTF-8 JSON text frames and binary frames for source bytes.
- **Limits**: Enforce configured maximum message, upload, connection, and per-user
  concurrency limits. A baseline upload cap is deployment-configured before
  release; do not rely only on `Content-Length`.

Access tokens MUST NOT be placed in the URL or logged. The server MUST NOT emit
submission data before authentication and authorization succeed.

## Envelope conventions

Client and server JSON events use:

```json
{
  "type": "client.message",
  "request_id": "opaque-random-id",
  "payload": {}
}
```

Server events use the same envelope shape and a server event type. `request_id`
is an opaque random correlation value, not an employee identifier. Do not log
event payloads, question text, field values, or identifiers associated with a
person.

## Client events

### `client.message`

```json
{
  "type": "client.message",
  "request_id": "random-id",
  "payload": {
    "text": "A concise idea description"
  }
}
```

`text` is required and bounded by the configured message limit. The server treats
all content as untrusted input.

### `client.source.begin`

```json
{
  "type": "client.source.begin",
  "request_id": "random-id",
  "payload": {
    "source_id": "random-id",
    "media_type": "application/pdf",
    "filename": "idea.pdf",
    "size_bytes": 12345
  }
}
```

Accepted source media types are PDF, DOCX, PPTX, WAV, MP3, and WebM. `filename`
is display metadata only; it MUST NOT determine a filesystem path. The server
validates type and declared size, then returns `server.source.ready` or rejects
the source. No source bytes are accepted before readiness.

### Binary source frames

After `server.source.ready`, the client sends one or more binary frames containing
raw bytes for the active `source_id`. The server appends bytes to a bounded
request-scoped memory buffer. It MUST NOT spool frames to disk.

### `client.source.commit`

```json
{
  "type": "client.source.commit",
  "request_id": "random-id",
  "payload": {
    "source_id": "random-id"
  }
}
```

Commit signals end-of-source; the server verifies received length, decodes and
parses in memory, and releases bytes and derived text at the end of processing.
Only one upload may be active per socket/session. A disconnect or timeout aborts
processing and releases its buffer.

## Server events

### `server.source.ready`

Acknowledges one accepted source and provides the `source_id`. No extracted value
is included.

### `server.source.completed`

Signals successful processing of the source. It contains no original content,
transcription, or dropped candidate value.

### `server.field.updated`

```json
{
  "type": "server.field.updated",
  "request_id": "random-id",
  "payload": {
    "field_key": "field_04",
    "value": "Safe accepted value",
    "origin": "ai_extracted",
    "status": "accepted"
  }
}
```

This event is sent only after NoFacts and field validation succeed and the value
is committed. Human-only fields MUST never appear with `origin: ai_extracted`.
Dropped candidates MUST produce no value event.

### `server.clarification`

```json
{
  "type": "server.clarification",
  "request_id": "random-id",
  "payload": {
    "field_key": "field_07",
    "question": "What outcome are you aiming to achieve?"
  }
}
```

For each successful turn where at least one mandatory field remains unfilled,
the server sends exactly one `server.clarification` event with the approved
single-question prompt for one unfilled mandatory field. The prompt is selected
from field metadata, not authored as free-form model prose. The server MUST NOT
send a second clarification event or bundle questions into another text field in
the same turn. If all mandatory fields are filled, this event is omitted.

### `server.submission.status`

Reports `in_progress`, `ready_for_human_declaration`, or `submitted`. The system
cannot transition to `submitted` based on AI-generated declaration fields.

### `server.error`

Contains a stable error code and a safe user-facing message. It MUST NOT include
source text, field values, PII, tokens, stack traces, or parser details that may
contain source content.

## Ordering, idempotency, and disconnects

- Process one client event at a time per session; reject unsupported event types.
- Reuse of a `request_id` MUST be idempotent for a retried message or source
  commit and MUST NOT create duplicate field updates.
- The service emits committed `server.field.updated` events before the associated
  turn's `server.clarification` or completion status.
- On disconnect, cancel work where safe, release all source buffers, and do not
  commit partial extraction. Authorized HTTP fallback may read current persisted
  field state after reconnect.
- Rejected values and source content MUST NOT be emitted or included in telemetry.

## Security and privacy

Validate schema, message size, upload size, Origin, identity, authorization, and
rate on every relevant boundary. Log only allowlisted outcome codes and random
correlation IDs. Enforce the no-disk guarantee at the application and ingress
layers, and verify deployment logging and buffering configuration.
