# Design: SDD 7 — Technical Debt, Observability, and Cross-Cutting Security

## Technical Approach

Implement the exploration recommendation in four incremental layers: refactor error handling first (pure refactor, zero behavior change), then sanitize WS/HTTP output, then add observability hooks, and finally bind upload artifacts to sessions. Each layer is independently mergeable and respects the existing wire format where possible.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| **1.A** structlog + Sentry (gated on `SENTRY_DSN`) | Industry default, ~150 LOC, requires Modal image bump | ✓ Chosen |
| 1.B stdlib logging + custom reporter | Zero SaaS deps, team owns the reporter | Rejected — more LOC, less reliable |
| **2.B** Session-bound filenames (`input/{session_id}/...`) | ~200 LOC, no S3 dependency, UUID4 unguessable | ✓ Chosen now; 2.A (S3 presigned) deferred to SDD 3 |
| **3.A** Centralize sanitization at `_build_event` + `comfy_client.stream_progress` | Two known leak points, ~80 LOC | ✓ Chosen |
| 3.B Regex-based response wrapper | Brittle false positives | Rejected |
| **4.A** Custom exception hierarchy + global FastAPI handler | Aligns with python-backend-mastery, single change point, ~150 LOC | ✓ Chosen |
| 4.B Per-flow handler classes | 4 implementations relocated, not DRY | Rejected |

## Data Flow

```
Client ──POST─→ Router ──(raises AppError)──→ Global Exception Handler
                    │                              │
                    │  service.enqueue/dispatch    │ builds sanitized JSONResponse
                    ↓                              │
              GenerationService                    │
                    │                              │
              validation / model check             │
                    │                              │
              modal.spawn ──→ Modal Task (_execute_generation)
                    │                   │
                    │         structlog.error / sentry.capture_exception
                    │                   │
              _build_event (sanitized) ←─ job_store
                    │
              WS /ws/generate/{job_id}
                    │
              event.result omitido (no image_path)
              event.error.detail sanitizado (sin node_id, paths absolutos)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/errors.py` | **Create** | `AppError` base + `ModelNotAllowedError`, `ModelNotCachedError`, `UnsupportedWorkflowError`, `SessionMismatchError` subclasses |
| `api/app.py` | Modify | Replace CORS `["*"]` → explicit allowlist; register global `AppError` handler; `structlog` + `sentry_sdk.init` (gated on `SENTRY_DSN`); `RequestIdMiddleware` |
| `api/src/features/generation/router.py` | Modify | Replace 4× duplicated try/except with `@map_service_errors` or `try: ... except AppError: raise` (let global handler process) |
| `api/src/features/generation/service.py` | Modify | `_build_event`: remove `image_path` from `completed` events; add `_sanitize_error_detail` to strip `/root/ComfyUI/` and `node {N}` patterns from error detail |
| `api/src/features/generation/modal_tasks.py` | Modify | Add `structlog` calls in `_execute_generation` catch blocks; `sentry_sdk.capture_exception` for `TimeoutError` and `Exception` branches |
| `api/src/shared/comfy_client.py` | Modify | `stream_progress`: stop appending `node_id`/`node_type` to public `error_message` |
| `api/src/shared/flows/base.py` | Modify | `ImageArtifact`: add `owner_session_id: Optional[str]` field |
| `api/src/shared/modal_config.py` | Modify | Add `structlog`, `sentry-sdk[fastapi]` to `comfyui_run_commands` pip installs |
| `api/src/features/generation/models.py` | Modify | `JobEventResult.image_path` → optional or removed; `JobEvent` validator relaxed for `completed` without `result` |
| `api/src/shared/job_store.py` | Modify | Add `volume_path` field alongside existing `image_path` (relative version for public WS) |

## Interfaces / Contracts

```python
# api/src/shared/errors.py — exception hierarchy
class AppError(Exception):
    status_code: int
    code: str
    user_message: str

class ModelNotAllowedError(AppError):       # 400
class ModelNotCachedError(AppError):         # 500
class UnsupportedWorkflowError(AppError):     # 422
class SessionMismatchError(AppError):         # 403

# Global handler in app.py
@fastapi_app.exception_handler(AppError)
async def app_error_handler(request, exc) -> JSONResponse: ...
```

```python
# CORS — app.py
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
fastapi_app.add_middleware(CORSMiddleware, allow_origins=cors_origins, ...)
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `AppError` → JSONResponse mapping | Parametrized pytest on status_code/code/detail |
| Unit | `_sanitize_error_detail` strips paths/node IDs | Table-driven: input string → expected output |
| Unit | `_validate_artifact_ownership` with `owner_session_id` | Enforce match; reject mismatch |
| Integration | Router endpoints raise `AppError` → global handler produces correct 400/422/500 shape | FastAPI `TestClient` preserves existing test wire format |
| Integration | CORS rejects `*` origin; allows localhost | `TestClient` with custom `Origin` header |
| Integration | `structlog` output is valid JSON; request_id propagates | Capture log output, assert correlation_id field |

## Migration / Rollout

- `SENTRY_DSN` unset → `sentry_sdk.init` no-ops; structured logs still work.
- `CORS_ORIGINS` unset → defaults to `http://localhost:3000` (safe dev default).
- `image_path` removal from WS: frontend already uses `GET /images/{job_id}` per exploration (line 309 router); no client migration needed.
- Session uploads: existing flows without `owner_session_id` remain accepted until SDD 3 migration.

## Open Questions

- [ ] Is the team ready with a Sentry DSN, or should we defer Sentry to SDD 8? (Design uses env-var gate — safe either way)
- [ ] Should the 422 body preserve the exact `{"detail": [{"type": "value_error", ...}]}` shape, or can we simplify to `{"error": {"code": "unsupported_workflow", "detail": ...}}`? (Current tests assert the verbose shape)
