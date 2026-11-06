# AWS deployment preparation

This directory documents the production configuration boundary. It does not
provision AWS resources or deploy code. No AWS credentials are needed in this
repository or in this guide.

## Proposed staging topology

- CloudFront default HTTPS hostname for the browser and same-origin `/api`,
  `/auth`, and `/health` paths.
- Private S3 origin for the compiled frontend.
- ECS Fargate API behind a private Application Load Balancer and CloudFront VPC
  Origin.
- Private RDS PostgreSQL, with credentials and application secrets in AWS
  Secrets Manager.
- GitHub Actions OIDC federation to a narrowly scoped AWS role for deploys from
  `develop`; no long-lived AWS access keys.

This topology is a proposal, not a verified deployment. Confirm CloudFront VPC
Origin support, ingress upload behavior, company security policy, service
availability, and current costs in `ap-south-1` before provisioning. Set an AWS
Budget and billing alerts first. ECS, RDS, load balancing, NAT, CloudFront,
storage, and data transfer can incur charges outside Free Tier.

## Entra application configuration

Have the Microsoft 365 / Entra administrator register a **single-tenant Web**
application. After the CloudFront distribution is created, add this exact
redirect URI under Web redirect URIs:

```text
https://<cloudfront-distribution-hostname>/auth/callback
```

Also register the app origin as a post-logout redirect URI:

```text
https://<cloudfront-distribution-hostname>/
```

The backend validates the ID token signature, issuer, audience, nonce, expiry,
and tenant through Authlib's OIDC client. It then issues an eight-hour,
HTTP-only, Secure, SameSite=Lax `oidc_session` cookie. The browser never receives
the Entra client secret or access token. The app requests only the `openid`
scope; no Microsoft Graph permissions are needed by the current code.

Set these backend environment variables through the ECS task definition. Keep
secret values in Secrets Manager and inject them as ECS secrets; do not place
them in Git, a Docker image, Terraform variables/state, or GitHub Actions logs.

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_ORIGIN` | Exact CloudFront origin, e.g. `https://d123example.cloudfront.net` |
| `ALLOWED_ORIGINS` | Same exact browser origin |
| `ENTRA_TENANT_ID` | Organization tenant GUID |
| `ENTRA_CLIENT_ID` | Entra application client GUID |
| `ENTRA_CLIENT_SECRET` | Secret from AWS Secrets Manager |
| `OIDC_SESSION_SIGNING_KEY` | Random secret of at least 32 bytes |
| `OIDC_FLOW_SIGNING_KEY` | A different random secret of at least 32 bytes |
| `DATABASE_URL` | PostgreSQL URL sourced from Secrets Manager |
| `MAX_UPLOAD_BYTES` | `20971520` or lower |
| `AWS_REGION` | `ap-south-1` |
| `BEDROCK_MODEL_ID` | A model ID enabled and approved for this account and region |
| `BEDROCK_DATA_PROCESSING_APPROVED` | `true` only after review described below |
| `TRANSCRIBE_NO_RETENTION_APPROVED` | `true` only after review described below |
| `TRANSCRIBE_LANGUAGE_CODE` | Approved streaming language code, e.g. `en-IN` |

Do not set `AIMPLIFY_LOCAL_DEV` in AWS. Production startup fails closed if Entra
or PostgreSQL configuration, AWS provider settings, or explicit provider data
processing approvals are absent. Rotating either signing key invalidates
existing browser sessions.

The backend uses the ECS task role and does not require AWS access keys. Scope
the role to `bedrock:InvokeModel` for the selected model and the required Amazon
Transcribe streaming action. Do not grant S3 permissions for audio ingestion.

Amazon Bedrock receives conversation/document text through the Converse API.
Disable model invocation logging in `ap-south-1` so prompts and outputs are not
copied to CloudWatch Logs or S3. Confirm the selected model's data handling and
retention terms with the AWS and company administrators; account-level data
retention controls are region-, model-, and API-dependent and are not verified
by this application. Amazon Transcribe receives audio as a streaming request.
The app converts WAV, MP3, and WebM in memory to 16 kHz mono PCM using FFmpeg
stdin/stdout pipes. It does not stage audio in S3 or write audio temporary
files. A prerecorded audio request takes approximately the audio duration to
transcribe. Set `BEDROCK_DATA_PROCESSING_APPROVED=true` and
`TRANSCRIBE_NO_RETENTION_APPROVED=true` only after reviewing the applicable AWS
terms and company policy. The Transcribe flag must reflect an explicit
no-retention approval; application-side transient handling alone does not
establish AWS-side retention behavior.

## Release blockers

- No live AWS call has been made from this repository. Verify model availability,
  permissions, language support, cost, service quotas, and behavior using the
  intended AWS account before production.
- The no-disk ingestion tests cover the application/parser boundary, not
  CloudFront, the load balancer, or the container platform. Complete the
  external-ingress tests in [the ingress release gate](../ingress/README.md)
  before sending employee uploads through a production edge.
- The pinned [AWS Transcribe Streaming Python SDK](https://github.com/awslabs/aws-sdk-python/tree/develop/clients/aws-sdk-transcribe-streaming)
  is currently marked experimental. Validate it with real short audio and the
  intended `ap-south-1` task role, and accept its maturity risk before enabling
  production transcription.
- Docker builds include FFmpeg and have not yet been validated in this
  environment. Build and exercise the image before deployment.
- This repository has no AWS infrastructure-as-code or deployment workflow yet.
  The backend image can be built from the repository root with:

  ```powershell
  docker build -f backend/Dockerfile -t aimplify-intake:local .
  ```

- `origin/main` does not currently contain the application. This checkout is
  `develop`; deploy from `develop` only after review, provider and data-retention
  decisions, CI, ingress validation, and company approval.

Do not provision production resources or invite employees until these blockers
are resolved. Nothing in this guide creates AWS resources.
