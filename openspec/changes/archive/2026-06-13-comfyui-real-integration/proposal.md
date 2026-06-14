# Proposal: ComfyUI Real Integration

## Intent

Replace the mocked `picsum.photos` generation path with real ComfyUI execution on Modal while preserving the current async API contract: `POST /generate`, `WS /ws/generate/{job_id}`, and frontend-consumable image results.

## Scope

### In Scope
- Run resolved JSON graph workflows through headless ComfyUI inside the Modal GPU task.
- Persist V1 outputs in the temporary Modal Volume and expose them through `GET /images/{job_id}`.
- Emit granular WebSocket states: `booting_server`, `downloading_weights`, `generating`, numeric `progress`, `completed`, `error`.
- Enforce a strict allowed-model whitelist; unknown models fail immediately with HTTP 400.
- Apply a prudent hard timeout around server boot + inference, targeting 5 minutes.
- Expand tests first under Strict TDD for client progress parsing, model rejection, image serving, timeout, and task orchestration.

### Out of Scope
- S3/R2 or permanent object storage; deferred to V2.
- Arbitrary runtime model downloads or user-provided model URLs.
- Separate always-warm ComfyUI Modal service; revisit if cold start latency is unacceptable.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `image-generation`: Replace mock completion with real ComfyUI execution, granular progress states, timeout failure, and served image result URL/path.
- `model-weight-caching`: Restrict model access to a pre-approved whitelist and pre-cached Modal Volume assets; reject unknown models before spawning inference.

## Approach

Use the exploration recommendation: enhance `ComfyUIClient` for WebSocket progress and output discovery, update `run_generation` to boot/verify ComfyUI on localhost, send the resolved graph, stream JobStore updates, read output from the Volume, and return a backend-served image reference. Keep routers thin and place orchestration in service/task/client layers.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/features/generation/modal_tasks.py` | Modified | Replace mock sleep/result with ComfyUI boot, prompt execution, timeout, cleanup. |
| `api/src/shared/comfy_client.py` | Modified | Parse progress/error messages and resolve output images. |
| `api/src/features/generation/router.py` | Modified | Add `GET /images/{job_id}` and expose richer WS events. |
| `api/src/features/generation/service.py` | Modified | Validate model whitelist before spawning Modal task. |
| `api/src/shared/workflows/cache.py` | Modified | Enforce pre-cached allowed models only for V1. |
| `api/src/tests/` | Modified | TDD coverage for all changed behavior. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cold start exceeds UX expectations | Med | Emit boot/download states; enforce timeout; consider warm service in V2. |
| GPU/process leaks | Med | Explicit subprocess cleanup and terminal error states. |
| Temporary Volume is not durable | Med | Document V1 limitation; defer object storage to V2. |

## Rollback Plan

Restore the previous mock `run_generation` behavior and remove/disable `GET /images/{job_id}` routing. Existing `POST /generate` and WebSocket contracts remain compatible.

## Dependencies

- Modal GPU runtime, temporary Modal Volume, ComfyUI repo/dependencies, pre-cached whitelisted model weights.

## Success Criteria

- [ ] Unknown model requests return HTTP 400 before Modal inference starts.
- [ ] Valid jobs emit granular WS updates and complete with a served image reference.
- [ ] Long-running jobs fail safely at the configured timeout.
- [ ] Test suite passes with Strict TDD coverage for new behavior.
