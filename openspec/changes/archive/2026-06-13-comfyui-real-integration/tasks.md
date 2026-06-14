# Tasks: ComfyUI Real Integration

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500-700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | chained-pr |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Model policy + cache boundary | PR 1 | Base branch = tracker; tests for whitelist/rejected cache miss first. |
| 2 | Real ComfyUI execution path | PR 2 | Base branch = PR 1; subprocess boot, timeout, progress relay, cleanup. |
| 3 | HTTP image serving + lifecycle wiring | PR 3 | Base branch = PR 2; image endpoint, WS state mapping, integration tests. |

## Phase 1: Foundation / Domain Boundaries

- [x] 1.1 Write failing tests in `api/src/tests/test_generation_service.py` for `model_not_allowed` before spawn and lora/checkpoint whitelist validation.
- [x] 1.2 Write failing tests in `api/src/tests/test_model_cache.py` for V1 cache hits/misses returning `model_not_cached` without runtime downloads.
- [x] 1.3 Update `api/src/features/generation/models.py` and `api/src/shared/workflows/models.py` schemas only after tests define the new error codes and event enum.

## Phase 2: Core Implementation

- [x] 2.1 Implement whitelist loading/validation in `api/src/shared/workflows/cache.py` from config/env, rejecting unknown checkpoint/lora IDs.
- [x] 2.2 Replace mock generation in `api/src/features/generation/service.py` with pre-spawn model validation and `run_generation.spawn(...)` gating.
- [x] 2.3 Implement ComfyUI boot/readiness/timeout cleanup in `api/src/features/generation/modal_tasks.py` with `Popen`, process-group shutdown, and 300s deadline.
- [x] 2.4 Update `api/src/shared/comfy_client.py` to parse ComfyUI WS events, queue prompts, and resolve output filenames from prompt history.

## Phase 3: Integration / Wiring

- [x] 3.1 Wire `api/src/shared/modal_config.py` to mount the image volume at `/root/ComfyUI/output` alongside model storage.
- [x] 3.2 Add `GET /images/{job_id}` in `api/src/features/generation/router.py` with binary file responses and `image_not_found` / `job_not_found` errors.
- [x] 3.3 Update `api/src/shared/job_store.py` and `api/src/features/generation/service.py` to persist `progress`, `image_path`, terminal errors, and granular WS events.

## Phase 4: Testing / Verification

- [x] 4.1 Add unit tests for subprocess cleanup, timeout termination, and readiness polling in `api/src/tests/test_modal_tasks.py`.
- [x] 4.2 Add websocket and service tests in `api/src/tests/test_generation_router.py` and `api/src/tests/test_e2e_generation.py` for booting/downloading/generating/progress/completed/error.
- [x] 4.3 Add FastAPI tests for `GET /images/{job_id}` returning PNG/JPEG bytes and the correct 404 error codes.

## Phase 5: Cleanup / Documentation

- [x] 5.1 Align any docstrings/comments in touched files with the new V1 boundary: no runtime model downloads, pre-cached Volume only.
- [x] 5.2 Remove mock-path leftovers and dead branches from generation flow once the real ComfyUI path is covered by tests.

## Phase 6: Verification Remediation

- [x] 6.1 Fix cache boundary bypass: enforce physical cache presence in `GenerationService.enqueue_modal_work()` before `run_generation.spawn()` and map `ModelNotCachedError` to HTTP 500 `model_not_cached` in the router.
- [x] 6.2 Fix disconnected WebSocket: call `ComfyUIClient.connect()` before streaming and `ComfyUIClient.close()` during cleanup in `_execute_generation()`.
- [x] 6.3 Fix fake timeout: wrap blocking HTTP/WS calls with per-call deadlines so the 300s hard timeout is actually enforced; use `asyncio.wait_for` around the websocket iterator.
- [x] 6.4 Add/update tests that expose the three flaws and verify the fixes (cache miss → HTTP 500, `connect()`/`close()` lifecycle, `asyncio.wait_for` + socket timeouts).
