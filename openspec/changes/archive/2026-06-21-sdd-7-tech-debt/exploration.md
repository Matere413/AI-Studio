# Exploration: sdd-7-tech-debt

## Goal

Pay down the technical debt surfaced while shipping SDD 2 (atomic flows). The
plan calls for four concrete fixes:

1. **Observability** — capture hardware failures (A100 OOM, missing custom
   nodes, timeouts) with structured logs and an alert channel.
2. **Volume security** — artifacts under `input/` must be bound to a session or
   cryptographically signed, not accessible by guessing a path.
3. **Error sanitization** — stop returning internal server paths and raw
   ComfyUI node IDs to the frontend.
4. **Refactor** — collapse the duplicated 422/500/400 try/except blocks in
   `api/src/features/generation/router.py` into a single middleware/decorator.

This document audits each area, lists the exact files/leak points, and compares
candidate solutions before the proposal phase.

## Current State

### Pipeline shape (unchanged from SDD 2)

```
Client (Next.js)                        Modal
   │                                      │
   │ POST /generate  (request/prompt)     │
   │ ───────────────────────────────────► │ FastAPI (api/app.py)
   │                                      │  └─ generation_router
   │                                      │     └─ GenerationService
   │                                      │        └─ WorkflowEngine
   │                                      │        └─ run_generation.spawn
   │ ◄── 202 + job_id                     │
   │ WS /ws/generate/{job_id} ──────────► │ _boot_comfyui → ComfyUIClient
   │ ◄── progress / completed             │   stream_progress() → job_store
   │ GET /images/{job_id}                 │
   │ ───────────────────────────────────► │ image_volume.reload() + FileResponse
```

The router (`api/src/features/generation/router.py`) is the only HTTP surface
today. It has four `POST` endpoints, one `GET`, and one `WS`.

### Area 1 — Observability (status: ABSENT)

There is no structured logging and no error reporting in the codebase:

| Location | Current behavior |
|---|---|
| `api/src/shared/comfy_client.py:117, 152, 225, 229` | `print(f"DEBUG ...")` to stdout. No log level, no formatter, no correlation id. |
| `api/src/features/generation/modal_tasks.py:55-56` | `subprocess.Popen(..., stdout=sys.stdout, stderr=sys.stderr)` — ComfyUI's own stdout is piped through, but no log wrapper. |
| `api/src/features/generation/modal_tasks.py:280-292` | `except TimeoutError` and `except Exception` swallow and write to `job_store` with `error_code`/`error_detail`. No log line. |
| `api/src/features/generation/router.py` | No `logging.getLogger` calls. No request id. No metrics. |
| `api/app.py` | No middleware other than `CORSMiddleware`. |
| `api/src/shared/job_store.py:62, 70` | `except Exception: return None` — silently swallows. |

There is **no** `sentry-sdk`, `structlog`, `prometheus_client`, `opentelemetry`,
or `logging` import anywhere in `api/`. Hardware failures (A100 OOM, missing
custom nodes) are only discoverable by reading the `JobEvent.error.detail`
field on a specific job — no alert, no aggregate, no on-call signal.

`_classify_comfyui_error` in `modal_tasks.py:93-121` already produces a clean
error code (`node_missing`, `gpu_oom`, `no_face_detected`, `comfyui_execution_failed`),
but the code is written into the job store and never logged.

### Area 2 — Volume security (status: PATH-BASED ONLY)

The `input_volume` is `comfy-input-disk` (`api/src/shared/modal_config.py:76`).
It is mounted at `/root/ComfyUI/input` in the Modal container. Today, **no
HTTP endpoint writes to this volume** — the only image-input path is
`image_base64` inside `flux2_editing`, which the engine injects as a ComfyUI
`LoadImageFromBase64` payload. So `input/` is reserved for "future user uploads"
and is currently empty in production.

The check that does exist is `_validate_artifact_ownership` in
`api/src/features/generation/service.py:170-209`:

```python
if art.source_job_id:
    job = self._store.get_job(art.source_job_id)
    if job is None or job.get("status") != "completed":
        raise ValueError(...)
    image_path = job.get("image_path")
    if image_path:
        art.volume_path = image_path  # override — defense against path injection
    elif not art.volume_path.startswith("input/"):
        raise ValueError(...)
elif not art.volume_path.startswith("input/"):
    raise ValueError(...)
```

This guards against path traversal (`/root/...` is rejected by
`ImageArtifact._validate_not_absolute` in `flows/base.py:77-89` and
`..` is rejected by `_validate_path_traversal` at lines 65-74), but it does
**not** bind an artifact to a user identity. Any client that knows or guesses
`input/<file>.png` can pass it as a composition/identity/extraction input.
There is no auth middleware (`grep` for `auth|user|token|hmac` in
`api/src/shared` returns nothing). `app.py:15-21` has
`allow_origins=["*"]` + `allow_credentials=True` — incompatible per the CORS
spec and not a security-grade policy.

The `JobStore` uses `modal.Dict.from_name("api-blanca-jobs", create_if_missing=True)`
(`api/src/shared/job_store.py:14`). There is no ACL on the dict — any
container in the same Modal app can read/write any job_id.

### Area 3 — Error sanitization (status: LEAKS PRESENT)

Two distinct leaks confirmed by reading the WS contract in
`api/src/features/generation/models.py:88-112` (`JobEvent` + `JobEventResult`):

**Leak 3a — absolute server path in `result.image_path`.**
`api/src/features/generation/service.py:334-337`:

```python
if event_type == "completed":
    event["result"] = {"image_path": job["image_path"]}
```

`job["image_path"]` is set in `modal_tasks.py:247-275` to a value resolved by
`ComfyUIClient.resolve_output_path` (`comfy_client.py:206-243`), which returns
`os.path.join("/root/ComfyUI/output", ...)` — an **absolute container path**.
This is broadcast to the frontend on the WebSocket on every `completed` event.
The frontend is supposed to use `GET /images/{job_id}` (the router does this
correctly at lines 308-309), but the absolute path is still in the payload.

**Leak 3b — ComfyUI node IDs in `error.detail`.**
`api/src/shared/comfy_client.py:178-198`:

```python
elif msg_type == "execution_error":
    error_message = data.get("exception_message") or ...
    context_parts = []
    exception_type = data.get("exception_type")
    node_id = data.get("node_id")
    node_type = data.get("node_type")
    if exception_type: context_parts.append(str(exception_type))
    if node_id:        context_parts.append(f"node {node_id}")
    if node_type:      context_parts.append(str(node_type))
    if context_parts:
        error_message = f"{error_message} ({', '.join(context_parts)})"
    yield {"event": "error", "message": error_message, ...}
```

The `message` here becomes `JobEvent.error.detail` (via
`modal_tasks.py:225-235` → `job_store.aupdate_job` → `service._build_event`
at lines 336-337). The frontend receives strings like
`"RuntimeError: tensor mismatch (node 19, KSamplerAdvanced)"`. `19` and
`KSamplerAdvanced` are internal ComfyUI graph topology — they tell a hostile
client the exact workflow template used.

**Leak 3c — Modal container paths in `ModelNotCachedError.__str__`.**
`api/src/shared/workflows/cache.py:36-39` builds the message
`f"Model '{filename}' ({model_type}) is not cached in {models_dir}. V1 requires ..."`
where `models_dir` defaults to `/root/ComfyUI/models`. The router's 500
handler in `router.py:56-65` only forwards `exc.filename` today, so this
specific leak is **not exposed** to the client via HTTP. But the string is
also raised into `RuntimeError` chains inside the Modal task
(`modal_tasks.py:321, 384, 430`), which then go to `print`/`stderr`. If the
exception ever bubbles into a future error path or into Sentry breadcrumb
data, the path would be exposed.

The router's 500 currently does **not** leak — but it relies on a developer
remembering to scrub each exception class. There is no central guarantee.

### Area 4 — Router refactor (status: 4x DUPLICATION)

`api/src/features/generation/router.py` has the same try/except shape four
times. Comparing `/generate` (lines 26-96), `/generate/extraction` (99-149),
`/generate/composition` (152-203), and `/generate/identity` (206-257):

| Endpoint | ModelNotAllowedError → 400 | ModelNotCachedError → 500 | ValueError "unsupported_workflow" → 422 | ValueError fallback → 422 |
|---|---|---|---|---|
| `/generate` | ✓ lines 46-55 | ✓ lines 56-65 | ✓ lines 66-94 | ✓ line 95 |
| `/generate/extraction` | ✓ lines 112-121 | ✓ lines 122-131 | ✓ lines 132-147 | ✓ line 148 |
| `/generate/composition` | ✓ lines 166-175 | ✓ lines 176-185 | ✓ lines 186-201 | ✓ line 202 |
| `/generate/identity` | ✓ lines 220-229 | ✓ lines 230-239 | ✓ lines 240-255 | ✓ line 256 |

The 422 "unsupported_workflow" body is the most repetitive — same 12-line
`{"detail": [{"type": "value_error", "loc": ["body", "workflow"], ...}]}`
shape is hand-rolled four times with minor wording differences (the `/generate`
version uses `message.split(": ", 1)`; the three flow versions use
`str(exc).split(": ", 1)`). The test suite codifies this duplication — see
`api/src/tests/test_generation_router.py:120-127` (`test_legacy_workflows_return_422`)
and the per-flow error tests at 477-490, 502, 714-749.

The 400 and 500 branches also vary in the field name (`"error": {"code": ..., "detail": ...}`)
vs FastAPI's default `{"detail": ...}`. Adding a fifth endpoint means
copy-pasting 30 more lines and re-deriving the 422 detail list.

`app.py` registers no global exception handler, so any exception that escapes
these blocks becomes a 500 with FastAPI's default body — which **does** leak
the traceback in debug mode.

## Affected Areas

| Path | Why it is affected |
|---|---|
| `api/src/features/generation/router.py` | Source of 4× duplication; needs central handler. |
| `api/src/features/generation/service.py` | `_build_event` (lines 308-344) builds the WebSocket payload that leaks `image_path` and `error.detail`. |
| `api/src/features/generation/modal_tasks.py` | `_classify_comfyui_error`, `_execute_generation` except blocks are the natural log points. |
| `api/src/shared/comfy_client.py` | `stream_progress` is where `node_id`/`node_type` get appended to the error message. |
| `api/src/shared/flows/base.py` | `ImageArtifact` model needs an `owner` / `signed_by` field for area 2. |
| `api/src/shared/job_store.py` | The error_code/error_detail fields are the canonical sink for hardware failures. |
| `api/src/shared/modal_config.py` | Image build needs `sentry-sdk` and the new `structlog` deps; the run_commands block has to be appended (pinning a version is the precedent — see `comfyui_controlnet_aux` checkout). |
| `api/app.py` | Add a logging filter, a Sentry init hook, and register the central exception handler. |
| `api/src/features/generation/models.py` | `JobEventResult.image_path` either becomes a `volume_path` (sanitized) or gets replaced by a `download_url` / signed URL. |
| `openspec/specs/image-generation/` | New requirement: error sanitization + observability hooks. |
| `openspec/specs/atomic-flows/` (new) | New requirement: session-bound or signed `ImageArtifact` ownership. |
| `openspec/specs/workflow-engine/` (existing) | Delta: error code `node_missing` / `gpu_oom` are already documented; nothing to add here. |

## Approaches

### Area 1 — Observability

#### Option A — `structlog` + Sentry SDK (recommended)

- Add `structlog` (with `structlog.stdlib.LoggerFactory`) at the FastAPI app
  level. JSON renderer in production, `ConsoleRenderer` in dev.
- Add `sentry-sdk[fastapi]` and call `sentry_sdk.init(dsn=os.environ["SENTRY_DSN"])`
  in `app.py` before the FastAPI app is constructed. `FastApiIntegration`
  hooks every request automatically.
- In `modal_tasks._execute_generation` catch blocks: `logger.error("generation_failed",
  job_id=..., error_code=..., exc_info=True)` and `sentry_sdk.capture_exception(exc)`.
- Add a `request_id` middleware that reads `X-Request-Id` or generates a UUID4
  and binds it to a `contextvars` var so every log line in a single request
  correlates.
- For hardware alerts: Sentry alert rules on `error_code in {gpu_oom, node_missing,
  timeout}` with a 1/hour threshold → Slack/PagerDuty webhook.

  - **Pros**: industry default, JSON logs are Sentry-friendly, PII scrubbing is
    built into `sentry_sdk.init` (`send_default_pii=False` is the default).
  - **Cons**: Sentry DSN is an env var the team doesn't have today; Modal image
    needs `sentry-sdk` added to `pip install` in `comfyui_run_commands`.
  - **Effort**: Low–Medium (~150 LOC + 1 image build bump).

#### Option B — stdlib `logging` + custom HTTP reporter

- Configure `logging.basicConfig` with a JSON formatter.
- Implement a small `ErrorReporter` that POSTs critical errors (OOM, timeout,
  node_missing) to a webhook the team owns.

  - **Pros**: zero new SaaS dependencies, full control.
  - **Cons**: rebuilds what Sentry gives for free; the team becomes the on-call
    for the reporter itself.
  - **Effort**: Medium (~250 LOC, plus a webhook receiver).

#### Option C — OpenTelemetry only (no error reporting)

- Add `opentelemetry-sdk` and export traces to Honeycomb/Tempo.

  - **Pros**: future-proof if/when the team adopts OTel.
  - **Cons**: traces are not alerts. Hardware failures still need a log/error
    sink. Solves half the problem.
  - **Effort**: Medium (~200 LOC).

### Area 2 — Volume security

#### Option A — Signed URLs (S3/R2) as the only handoff path (recommended)

- Introduce `POST /uploads/sign` that returns a presigned PUT URL pointing to
  `s3://bucket/users/{user_id}/{upload_id}.png`. The client uploads directly to
  S3 and receives a key.
- The flow requests accept `ImageArtifact(upload_key=..., media_type=...)`
  (the existing `volume_path` field is renamed/split).
- A small `storage.py` layer resolves `upload_key` to a `s3://` URL that
  ComfyUI can fetch (or downloads it into the `input/` volume under a
  server-controlled subdir like `input/{user_id}/{job_id}.png`).
- The new `/uploads/sign` endpoint is the only thing that needs auth — every
  other endpoint keeps its current contract.

  - **Pros**: no path guessing works, audit trail in S3, removes the
    `input/<arbitrary>.png` attack surface entirely. Aligns with the
    development plan's SDD 3 (object storage).
  - **Cons**: requires S3 credentials and a bucket. Pushes the upload step
    back to the client (good) but means SDD 7 ships a thin auth/identity
    layer before SDD 3 lands the full S3 pipeline.
  - **Effort**: Medium (~300 LOC + S3 setup).

#### Option B — Session-bound filenames (no S3, no crypto)

- Add a `Session` model (`session_id: UUID4`) and a `POST /sessions` endpoint
  that mints one.
- Upload path: `POST /uploads/{session_id}` writes the file into
  `input/{session_id}/{filename}.png` on the `input_volume`.
- `ImageArtifact` gains an `owner_session_id` field; `_validate_artifact_ownership`
  enforces that the field matches the request's session header.

  - **Pros**: no S3 dependency; smaller diff; works on the existing `input/`
    volume. Stops the "guess a path" attack because the path is
    `input/{session_id}/...` and session_id is unguessable.
  - **Cons**: still server-side filesystem, not a durable signed URL. The
    signature in the plan ("firmados criptográficamente") is not literal.
  - **Effort**: Low–Medium (~200 LOC).

#### Option C — HMAC-signed URL parameters (no S3, no sessions)

- Client requests `POST /uploads/sign?filename=foo.png` and receives
  `/uploads/input/{filename}.png?expires=...&sig=HMAC-SHA256(secret, filename+expires)`.
- The upload endpoint validates the signature, writes to `input/{filename}.png`.
- The flow requests accept `ImageArtifact` with the same signed URL.

  - **Pros**: minimal contract change, works with any client, no user identity
    required for MVP.
  - **Cons**: signing is shared-secret; no per-user audit trail. Still
    filesystem.
  - **Effort**: Low (~150 LOC).

### Area 3 — Error sanitization

#### Option A — Centralize at the JobEvent + HTTP layer (recommended)

- In `service._build_event` (line 308): replace
  `event["result"] = {"image_path": job["image_path"]}` with
  `event["result"] = {"volume_path": job["volume_path"]}` (relative, no
  `/root/...` prefix) **or** drop `image_path` from the event entirely and
  keep the contract that the client uses `GET /images/{job_id}`.
- Strip `node_id` and `node_type` from the `error_message` in
  `comfy_client.stream_progress`. Keep `exception_type` and a generic
  `exception_message` (already a sensible subset).
- Add a `_sanitize_error_detail(detail: str) -> str` helper in
  `src/shared/errors.py` that strips `/root/ComfyUI/...`, ComfyUI class
  names, and `node {N}` patterns. Apply it in `_build_event` before
  serializing.

  - **Pros**: one place to audit. The error detail never leaves the box in
    raw form. The image download path is still
    `GET /images/{job_id}` and works unchanged.
  - **Cons**: changes the public contract slightly (`image_path` →
    `volume_path` or removed). Frontend must follow.
  - **Effort**: Low (~80 LOC, all in `service.py` + `comfy_client.py`).

#### Option B — Add a `downscale` transform on the response

- Wrap every `JSONResponse` in a `safe_response` decorator that strips
  filesystem-looking strings and ComfyUI class names from any `detail` /
  `error` / `result` field.

  - **Pros**: one decorator covers all current and future endpoints.
  - **Cons**: regex-based sanitization is brittle (false positives). Better
    to fix the producer.
  - **Effort**: Low (~60 LOC) but lower confidence.

#### Option C — Use a separate "public" Pydantic model for the response

- Define `JobEventPublic` that omits `image_path` and keeps a curated
  `error: {code, message, user_message}` with no `detail`.

  - **Pros**: contract-first, schema enforces sanitization.
  - **Cons**: requires reworking every endpoint and the WS serializer.
    Overkill for the leak surface.
  - **Effort**: Medium (~200 LOC).

### Area 4 — Router refactor

#### Option A — Centralized exception handler via decorators (recommended)

- Define a custom exception hierarchy in `api/src/shared/errors.py`:
  - `class AppError(Exception)` with `code: str`, `status_code: int`,
    `user_message: str`.
  - `class ModelNotAllowedError(AppError)` (status 400, code `model_not_allowed`).
  - `class ModelNotCachedError(AppError)` (status 500, code `model_not_cached`).
  - `class UnsupportedWorkflowError(AppError)` (status 422, code
    `unsupported_workflow`, structured detail list).
- Register one `fastapi.exception_handler(AppError)` that builds the
  FastAPI-compatible 422 detail list from a single shape and applies the
  sanitization helper from Area 3.
- Decorate each router handler with `@map_service_errors` (or wrap the
  service calls in a `with _handle_app_errors():` context manager) so the
  router endpoints become 3–4 lines each.

  - **Pros**: aligns with the python-backend-mastery rule
    "Use custom exceptions and a global FastAPI exception handler to map
    them to HTTP status codes." Single point of change.
  - **Cons**: existing test suite codifies the per-endpoint shape
    (`test_generation_router.py:120-127` and the 4x error tests). The
    refactor MUST preserve the wire format to avoid a test rewrite.
  - **Effort**: Low–Medium (~150 LOC, mostly moving the existing try/except
    bodies into one place).

#### Option B — Per-flow handler classes

- One `FlowErrorHandler` class per atomic flow. The router instantiates the
  right one for each endpoint.

  - **Pros**: each flow owns its own mapping (good for SDD 2's per-flow
    feature modules).
  - **Cons**: still 4 implementations of the same idea, just relocated. Does
    not actually reduce duplication unless a base class is introduced, at
    which point it's Option A.
  - **Effort**: Low, but only superficially DRY.

#### Option C — Move the 422 body into a Pydantic-validated exception handler

- Subclass `HTTPException` with a `to_pydantic_response()` method that
  produces the structured detail list. Register one global handler.

  - **Pros**: type-safe; IDE autocomplete on `code` and `detail`.
  - **Cons**: more boilerplate than Option A; `HTTPException` semantics in
    FastAPI are subtle.
  - **Effort**: Medium.

## Recommendation

Adopt the **lower-effort, high-leverage combination**:

| Area | Pick | Why |
|---|---|---|
| 1 — Observability | **A** (structlog + Sentry) | Industry default, minimal LOC, alerting is the explicit goal. |
| 2 — Volume security | **B** (session-bound filenames) for the immediate fix, with **A** (signed S3 URLs) as the SDD 3 follow-up the plan already calls for. B is the smallest diff that removes the "guess a path" attack without requiring an S3 bucket today. |
| 3 — Error sanitization | **A** (centralize at `_build_event` + `comfy_client.stream_progress`) | The leaks are at two well-known spots. Fix the producers. |
| 4 — Router refactor | **A** (custom exception hierarchy + global handler) | Aligns with `python-backend-mastery` guidance, keeps the wire format, removes 4× duplication. |

### Phasing

To keep the 400-line PR budget honest, split SDD 7 into four chained PRs:

1. **PR 1 — Refactor (Area 4).** Introduce `AppError` hierarchy + global
   handler. Keep wire format identical. Existing tests should pass with
   zero changes. This is the seam for PRs 2–3.
2. **PR 2 — Sanitization (Area 3).** Strip `image_path` → `volume_path` (or
   remove), strip `node_id`/`node_type` from WS errors. Add
   `_sanitize_error_detail`. Update tests that assert on the old strings.
3. **PR 3 — Observability (Area 1).** Add `structlog`, `sentry-sdk`, request-id
   middleware, log lines in `modal_tasks._execute_generation`, Sentry
   `before_send` to scrub filesystem paths.
4. **PR 4 — Volume security (Area 2).** Add `Session` model + `POST /sessions`
   + `POST /uploads/{session_id}` + `owner_session_id` in `ImageArtifact`.
   Update `_validate_artifact_ownership` to require the match.

PR 1 is a pure refactor (no behavior change) — the safest to merge first.
PR 4 depends on PR 1 because the new error type is "session mismatch" which
should flow through the central handler.

### Why not all of Option C in area 2?

A signed-S3-only model is the right long-term answer, but it forces the
client to migrate to presigned PUTs before the rest of SDD 3 lands. The
session-bound filename gives 90% of the security win (no path guessing)
with a smaller diff and is forward-compatible — when SDD 3 lands, the
session can become the S3 prefix and the same `owner_session_id` field
keeps working.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Test suite breaks on wire-format changes (Area 3) | Med | Med | Update affected tests; add a contract test for the new public shape. |
| Sentry DSN missing in dev | Low | Low | `sentry_sdk.init` is a no-op if `dsn=None`; gate on env var. |
| `sentry-sdk` adds 5+ MB to Modal image | Low | Low | Already in `sentry-sdk[fastapi]` wheel; cold-start cost is sub-second. |
| Session-bound filenames still allow `session_id` enumeration (B) | Low | Med | UUID4 (122-bit) is unguessable; the `/uploads` endpoint enforces a CSRF token and rate limit. |
| `_sanitize_error_detail` strips legit ComfyUI output containing `node 6` | Med | Low | Sanitization targets `error_message` only, not the graph JSON. Whitelist `node {N}` removal to the error path. |
| `structlog` JSON output confuses existing `print` debugs | Low | Low | Keep the `print` debugs in `comfy_client` until the sanitization PR rewrites that path. |
| Chained PRs grow past 400-line review budget | Med | Med | Four small PRs each under 400 lines, mapped to the four goals above. |
| Existing `test_e2e_generation.py` asserts `/root/ComfyUI/output/img.png` in `result.image_path` | Med | Med | Update assertion to `/root/ComfyUI/output/img.png` → `output/img.png` (or whatever the sanitized form is). |
| Central handler breaks FastAPI's built-in `RequestValidationError` (422) | Med | Med | Do not catch `RequestValidationError` in the `AppError` handler; let FastAPI's default run. |
| `JobStore` distributed `modal.Dict` is not user-scoped | High | Med | Out of scope for SDD 7 — the current V1 has no auth at all. Defer per-user keying to SDD 3 (object storage + identity). |

## Open Questions for the User

1. **Sentry account** — is the team ready to provision a Sentry project and
   expose a DSN? If not, fall back to stdlib `logging` (Option 1.B) and
   defer Sentry to SDD 8.
2. **Session vs signed-URL priority** — should SDD 7 ship the session-bound
   filename path now, or block on S3 setup so we land signed-URLs in one
   shot? The plan's wording ("firmados criptográficamente") leans toward
   signed, but that is a larger dependency.
3. **`image_path` vs `volume_path` naming** — do we rename the WS event
   field, or remove it entirely and force the client to use
   `GET /images/{job_id}`? The frontend already calls that endpoint
   (verified in `view2-design-rebuild/exploration.md`), so removing the
   field is the cleanest.
4. **CORS hardening** — `allow_origins=["*"]` + `allow_credentials=True` is
   invalid. Is fixing CORS in scope, or do we leave it for a follow-up?
5. **`request_id` propagation** — should the request id flow into the
   Modal function so logs across the WS and the Modal function are
   correlatable? `modal.spawn` accepts kwargs, so yes, but it adds one
   field to every spawn signature.

## Ready for Proposal

**Yes, with conditions.**

- The 4 audit areas are concrete and each has at least 2 viable options.
- The 4-PR chained slice plan keeps the 400-line review budget.
- The recommendation (1.A + 2.B + 3.A + 4.A) is grounded in the existing
  python-backend-mastery rules and the project's strict TDD
  (`openspec/config.yaml:55-65`).
- The proposal phase should answer the 5 open questions above before
  locking the per-PR approach.

The next phase (`sdd-propose`) should write:
- `proposal.md` — capability changes, in/out of scope, success criteria.
- `specs/error-handling/spec.md` (new) — central handler, sanitized fields.
- `specs/observability/spec.md` (new) — log shape, Sentry hooks, alert rules.
- `specs/artifact-security/spec.md` (new) — session-bound artifacts.
- Delta to `specs/image-generation/spec.md` — `volume_path` instead of
  `image_path` in the public event.
