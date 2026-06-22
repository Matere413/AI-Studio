# Proposal: SDD 7 Technical Debt, Observability, and Cross-Cutting Security

## Intent

Pay down SDD 2 debt that makes Modal generation failures hard to diagnose and exposes internal implementation details. This change adds production observability, removes leaked paths/node IDs, tightens interim artifact ownership, restricts CORS, and centralizes repeated HTTP error handling.

## Scope

### In Scope
- Add `structlog` and optional `sentry-sdk[fastapi]`; Sentry is disabled when `SENTRY_DSN` is unset.
- Remove absolute `image_path` from WebSocket payloads; keep image retrieval via `GET /images/{job_id}`.
- Sanitize raw ComfyUI `node_id` and internal paths from public error details.
- Bind `input/` uploads/artifacts to a Session UUID until SDD 3 S3 integration lands.
- Replace wildcard CORS with localhost plus standard production domains.
- Consolidate duplicated 422/500 HTTP exception mapping into a central app handler/middleware.

### Out of Scope
- Full S3/R2 signed-upload pipeline from SDD 3.
- Authentication, per-user ACLs, or Modal Dict tenant isolation.
- Metrics/tracing beyond structured logs and Sentry error reporting.

## Capabilities

### New Capabilities
- `observability`: structured request/job logs, optional Sentry capture for GPU OOM, missing nodes, timeouts, and uncaught FastAPI errors.
- `app-error-handling`: centralized FastAPI error mapping and public-detail sanitization.
- `api-security`: CORS allowlist and session-scoped interim upload ownership.

### Modified Capabilities
- `image-generation`: completed WS events no longer include `result.image_path`; public errors are sanitized.
- `atomic-flows`: `ImageArtifact` for `input/` paths requires matching Session UUID ownership.
- `generative-ai-studio-frontend`: frontend continues deriving image URLs from `job_id`, not WS `image_path`.

## Approach

Implement the exploration recommendation: central error primitives first, then producer-side sanitization, observability hooks, and session-bound artifact checks. Preserve existing wire formats where possible except the intentional removal of `result.image_path`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/app.py` | Modified | CORS allowlist, Sentry init, handlers/middleware. |
| `api/src/features/generation/router.py` | Modified | Remove repeated try/except blocks. |
| `api/src/features/generation/service.py` | Modified | Build sanitized WS events. |
| `api/src/features/generation/modal_tasks.py` | Modified | Structured failure logs/Sentry capture. |
| `api/src/shared/comfy_client.py` | Modified | Stop adding raw node metadata to public errors. |
| `api/src/shared/flows/base.py` | Modified | Session-bound `ImageArtifact` validation. |
| `api/src/shared/modal_config.py` | Modified | Add runtime dependencies. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Frontend/tests expect `result.image_path` | Med | Update contract/tests to use `job_id` image URL. |
| Sentry missing in dev/prod | Low | Gate on `SENTRY_DSN`; logs still work. |
| Central handler changes 422 shape | Med | Preserve FastAPI-compatible 422 body. |

## Rollback Plan

Revert the change set or disable Sentry by unsetting `SENTRY_DSN`. If session upload checks block valid users, temporarily reject `input/` artifacts while keeping generated `source_job_id` handoff active.

## Dependencies

- Python packages: `structlog`, `sentry-sdk[fastapi]`.
- Environment: optional `SENTRY_DSN`, explicit CORS production domain list.

## Success Criteria

- [ ] GPU OOM, missing node, timeout, and uncaught app errors are logged structurally and captured by Sentry when configured.
- [ ] WS payloads expose no absolute `image_path`, raw `node_id`, or internal ComfyUI paths.
- [ ] `input/` artifacts are rejected unless bound to the request Session UUID.
- [ ] CORS no longer allows `*`.
- [ ] Router endpoints share one central 422/500 mapping path with preserved public error shapes.
