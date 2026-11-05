# Ingress No-Disk Release Gate

The API reads uploads from `Request.stream()` into request-scoped `BytesIO`
buffers. Its default maximum is 20 MiB (`MAX_UPLOAD_BYTES=20971520`). Configure
the ingress request limit to the same value or lower. Do not use multipart
parsing, request-body logging, or a disk-backed body buffer in front of the API.

## Required Deployment Settings

- Stream request bodies to the API without proxy request buffering. For Nginx,
  review `proxy_request_buffering off` and `client_max_body_size 20m`; size the
  in-memory client body buffer and concurrency limits together.
- Ensure an oversized body is rejected before any temporary-file spill. Do not
  rely on a temporary directory, container layer, or host path for uploads.
- Disable access logging for upload and WebSocket routes, or use an explicitly
  reviewed allowlist containing only method, route template, status, duration,
  and a random request ID. Never log cookies, authorization headers, filenames,
  query values, request/response bodies, source text, or extracted field values.
- Keep WebSocket frame logging disabled. Error and debug logs must not serialize
  request objects, parser inputs, provider responses, or exception payloads.
- Set process, container, and host diagnostics so request buffers cannot be
  written to disk through swap, core dumps, crash dumps, or temporary-file
  fallbacks. Apply upload concurrency and timeout limits to bound memory use.

These are deployment requirements, not verified settings in this repository. No
reverse proxy or ingress configuration is checked in.

## Release Verification

Do not release until all of these checks pass against the exact production
ingress image and configuration:

1. Send canary files for PDF, DOCX, PPTX, WAV, MP3, and WebM through the external
   ingress to the API, including malformed and maximum-size requests.
2. Observe filesystem syscalls and all configured temporary paths at the ingress
   and API processes. Fail if any source or derived bytes are written or spooled.
3. Scan application, proxy/access, error, and WebSocket logs for unique PII,
   token, filename, source-text, and extracted-value canaries. Fail on any match.
4. Confirm ingress and API body limits agree, rejected uploads leave no partial
   field state, and all in-memory buffers are released on success and failure.
5. Record the proxy version, effective configuration, test output, and approved
   accepted-data retention/deletion policy with the release evidence.

The automated API-to-parser contract is
`backend/tests/contract/ingestion/test_ingress_no_disk.py`. It validates the
application boundary and Python/OS file-opening paths; it does not substitute
for the external-ingress release checks above.