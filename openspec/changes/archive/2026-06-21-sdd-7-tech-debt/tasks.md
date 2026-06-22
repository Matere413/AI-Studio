# Tasks: SDD 7 — Technical Debt, Observability, and Cross-Cutting Security

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~515 lines (4 layers × ~100-165 lines each) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Error Handling) → PR 2 (Sanitization) → PR 3 (Observability + CORS) → PR 4 (Session Ownership + Frontend) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Error handling foundation: AppError hierarchy + global handler + router cleanup | PR 1 | base: main; pure refactor, zero behavior change |
| 2 | Output sanitization: strip paths/node_id from WS/HTTP errors + remove image_path from completed events | PR 2 | base: main after PR 1 merges; depends on AppError |
| 3 | Observability + CORS: structlog + Sentry (gated) + RequestIdMiddleware + CORS allowlist | PR 3 | base: main after PR 2 merges; mostly independent |
| 4 | Session ownership + frontend contract: owner_session_id validation + derive image URL from job_id | PR 4 | base: main after PR 3 merges; independent of layers 1-3 |

## Phase 1: Error Handling Foundation

- [x] 1.1 Create `api/src/shared/errors.py` with `AppError` base class (status_code, code, user_message) and subclasses: `ModelNotAllowedError` (400), `ModelNotCachedError` (500), `UnsupportedWorkflowError` (422), `SessionMismatchError` (403)
- [x] 1.2 Modify `api/app.py`: register global `register_app_error_handlers(fastapi_app)` that returns `JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "detail": exc.user_message}})`
- [x] 1.3 Modify `api/src/features/generation/router.py`: remove 4× duplicated try/except blocks via `_handle_service_errors()` context manager that converts to `AppError` → global handler
- [x] 1.4 Write unit tests: `test_errors.py` — AppError subclasses + JSONResponse mapping (status_code, code, detail shape)
- [x] 1.5 Write integration tests: `test_router_error_mapping.py` — all 4 endpoints produce correct 400/422/500 shape through global handler

## Phase 2: Output Sanitization

- [x] 2.1 Add `_sanitize_error_detail(detail: str) -> str` in `errors.py` strips `/root/ComfyUI/`, `node {N}`, and absolute paths using regex
- [x] 2.2 Modify `_build_event` in `service.py`: calls `_sanitize_error_detail` on error events before emitting
- [x] 2.3 Modify `comfy_client.py`: `stream_progress` stops appending `node_id`/`node_type` to public `error_message`
- [x] 2.4 Modify `models.py`: `JobEventResult.image_path` → optional; `JobEvent` validator relaxed for `completed` without `result`
- [x] 2.5 Modify `service.py`: `_build_event` removes `image_path` from `completed` events (client uses `GET /images/{job_id}`)
- [x] 2.6 Write unit tests: `test_sanitization.py` — `_sanitize_error_detail` with 7 cases (paths, node IDs, edge cases)
- [x] 2.7 Write integration/unit tests: verify WS `error` events contain no `node_id`; `completed` events omit `image_path`

## Phase 3: Observability + CORS

- [x] 3.1 Add `structlog`, `sentry-sdk[fastapi]` to Modal pip installs + `requirements-dev.txt`
- [x] 3.2 Create `api/src/shared/logging.py` with structlog JSON configuration; import in `app.py`, `modal_tasks.py`, `service.py`
- [x] 3.3 Add `RequestLogMiddleware` (UUID4 `correlation_id` + structlog binding) in `app.py`
- [x] 3.4 Request logging middleware (same as 3.3) emits structured `request` log with `method`, `path`, `status_code`, `duration_ms`, `correlation_id`
- [x] 3.5 Replace CORS `["*"]` → `cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")`
- [x] 3.6 Gate `sentry_sdk.init(dsn=..., integrations=[FastApiIntegration()])` on `SENTRY_DSN` presence in `app.py`
- [x] 3.7 Add `structlog.error()` + `_capture_sentry(job_id, error_code, exception)` in `modal_tasks.py` catch blocks
- [x] 3.8 Add `_log.error("job_error", job_id=..., error_code=..., error_detail=...)` in `service.py` `_build_event`
- [x] 3.9 Write integration tests: `test_observability.py` — structlog JSON output, correlation_id propagation (7 tests)
- [x] 3.10 Write integration tests: CORS allowlist — accepts `http://localhost:3000`, rejects disallowed origins
- [x] 3.11 Write integration tests: Sentry gating logic — init called when DSN set, not called when unset

## Phase 4: Session Ownership + Frontend Contract

- [x] 4.1 Modify `api/src/shared/flows/base.py`: add `owner_session_id: Optional[str]` field to `ImageArtifact`
- [x] 4.2 Modify `api/src/shared/flows/base.py`: add `_validate_artifact_ownership(artifact, session_id)` that rejects `input/` paths unless `owner_session_id` matches request session
- [x] 4.3 Modify `api/src/features/generation/service.py`: call `_validate_artifact_ownership` before enqueuing generation
- [x] 4.4 Modify `api/src/shared/job_store.py`: add `volume_path` field alongside existing `image_path` (relative version for public WS)
- [x] 4.5 Modify frontend store/reducer: on `completed` event, derive image URL from `job_id` (`/api/images/{job_id}`) instead of consuming `result.image_path`
- [x] 4.6 Modify frontend workspace canvas: render result from `/api/images/{job_id}` via `next/image`
- [x] 4.7 Write unit tests: `_validate_artifact_ownership` with matching/mismatched/missing session segment
- [x] 4.8 Write integration tests: verify `input/` paths with mismatched session rejected with `error.code = "invalid_artifact"`; verify generated artifacts (with `source_job_id`) accepted regardless of session
