# HTTP Contract: AIMPLIFY Health and Fallback

All endpoints are versioned under `/api/v1`. Production traffic uses HTTPS.
Submission endpoints require an authenticated OIDC session and authorization
for the target submission. Mutating cookie-authenticated requests require the
configured CSRF protection. Error bodies and access logs MUST NOT expose PII,
tokens, source content, field values, or parser stack traces.

## Common error envelope

```json
{
  "error": {
    "code": "SOURCE_UNSUPPORTED",
    "message": "This source could not be processed.",
    "request_id": "opaque-random-id"
  }
}
```

The `request_id` is random and non-identifying. Error responses never echo
submitted text, filenames, raw parser messages, or rejected candidate values.

## Health

### `GET /health/live`

Process liveness only; it does not disclose environment, credentials, or
submission state.

**200 response**

```json
{
  "status": "live"
}
```

### `GET /health/ready`

Readiness for authenticated service dependencies. It reports only aggregate
availability; dependency details and credentials remain private.

**200 response**

```json
{
  "status": "ready"
}
```

**503 response** uses the common safe error envelope.

## Fallback endpoints

### `POST /api/v1/sessions`

Creates an in-progress submission using the authenticated subject and active
schema version. The subject is obtained from validated identity, not trusted from
the request body.

**201 response**

```json
{
  "session_id": "opaque-random-id",
  "status": "in_progress",
  "schema_version": "active"
}
```

### `POST /api/v1/sessions/{session_id}/messages`

Processes a chat message through the same graph, NoFacts gate, schema validation,
and one-question pacing as WebSocket input.

**Request**

```json
{
  "request_id": "opaque-random-id",
  "text": "A concise idea description"
}
```

**200 response**

```json
{
  "request_id": "opaque-random-id",
  "field_updates": [
    {
      "field_key": "field_04",
      "value": "Safe accepted value",
      "origin": "ai_extracted"
    }
  ],
  "clarification": {
    "field_key": "field_07",
    "question": "What outcome are you aiming to achieve?"
  },
  "status": "in_progress"
}
```

`clarification` is either one object or `null`, never an array. It is exactly one
approved single-question prompt for one unfilled mandatory field whenever any
mandatory field remains missing; it is `null` when none remain. A field update is
returned only after it has passed all gates and been committed. Human-only fields
are excluded from AI field updates.

### `POST /api/v1/sessions/{session_id}/sources/{media_type}`

Accepts one source as a streamed raw request body (`application/octet-stream` or
the validated media type), not multipart form data. `media_type` is one of `pdf`,
`docx`, `pptx`, `wav`, `mp3`, or `webm`. `X-Source-Name` is optional display
metadata and MUST NOT be used as a path. Apply configured byte and concurrency
limits while reading the body into memory. Do not use a framework path that
spools request content to disk.

The endpoint returns the same safe field update and clarification shape as the
message endpoint. Audio is transcribed transiently and neither audio nor
transcript is persisted. Rejected numeric claims are silently omitted.

**Success**: `200 OK` with the fallback response envelope.

**Unsupported or invalid source**: `400 Bad Request` with
`SOURCE_UNSUPPORTED` or `SOURCE_INVALID`.

**Over configured size limit**: `413 Payload Too Large` with `SOURCE_TOO_LARGE`.

**Processing dependency unavailable**: `503 Service Unavailable` with
`SOURCE_PROCESSING_UNAVAILABLE`; no partial values from the failed source are
committed.

### `GET /api/v1/sessions/{session_id}/fields`

Returns the authenticated user's persisted safe field state for reconnect and
HTTP fallback. It returns schema metadata and accepted values only; no source
bytes, transcript, raw chat, rejected candidates, or AI-generated human-only
values.

**200 response**

```json
{
  "session_id": "opaque-random-id",
  "schema_version": "active",
  "sections": [
    {
      "section_key": "section_01",
      "fields": [
        {
          "field_key": "field_04",
          "mandatory": true,
          "human_only": false,
          "value": "Safe accepted value",
          "origin": "ai_extracted"
        }
      ]
    }
  ],
  "status": "in_progress"
}
```

The response contains exactly six sections and 27 field definitions for the
selected schema version. Human-only field values can appear only after a human
has entered them.

### `PUT /api/v1/sessions/{session_id}/fields/{field_key}`

Updates one human-entry-only field. The request requires an authenticated OIDC
session, authorization for the submission, and an allowed `Origin`. The
`field_key` must be `declaration_accepted`, `submitter_signature`,
`date_of_submission`, or `reviewer_notes`; AI-writable fields are rejected.

**Request**

```json
{
  "value": "A value validated against the canonical field type"
}
```

Boolean declaration values use JSON booleans. Successful updates are persisted
with `origin: "human_entered"` and return only the updated field key, normalized
value, and origin. Invalid field values return a generic `422` response. The
service never routes these values through AI extraction.

## Status and error codes

| HTTP status | Codes | Meaning |
|---|---|---|
| `400` | `SOURCE_INVALID`, `SOURCE_UNSUPPORTED`, `REQUEST_INVALID` | Malformed request or unsupported source |
| `401` | `UNAUTHENTICATED` | Missing or invalid OIDC identity |
| `403` | `FORBIDDEN` | Identity cannot access this submission |
| `404` | `SESSION_NOT_FOUND` | Session does not exist or is not visible to caller |
| `409` | `REQUEST_CONFLICT` | Idempotency key reused for a different request |
| `413` | `SOURCE_TOO_LARGE` | Configured size limit exceeded |
| `422` | `VALIDATION_FAILED` | Safe schema/type validation failed |
| `429` | `RATE_LIMITED` | Request or concurrent-upload limit exceeded |
| `503` | `SOURCE_PROCESSING_UNAVAILABLE`, `SERVICE_UNAVAILABLE` | Required dependency unavailable |

Authentication, authorization, validation, throttling, and error paths follow the
same PII-free logging policy as WebSocket events.
