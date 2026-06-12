# Proposal: MVP Generation Endpoint

## Intent

Provide a production-ready base image generation API that accepts a text prompt, executes a ComfyUI JSON workflow on Modal GPU, and streams job progress back to the client via WebSocket. This unlocks the first usable B2B generation flow.

## Scope

### In Scope
- FastAPI ASGI app mounted via `modal.asgi_app` with HTTP + WebSocket routing
- `POST /generate` endpoint accepting a prompt and returning a `job_id`
- `WS /ws/generate/{job_id}` endpoint streaming progress/completion/error
- Modal GPU background function (`modal.function.spawn`) executing ComfyUI
- Feature-First package: `src/features/generation/` (router, services, models, modal_jobs)
- Pydantic schemas for request validation and response serialization

### Out of Scope
- Redis / PubSub real-time push (deferred; polling is sufficient for MVP)
- Image storage / presigned URL return (placeholder path only)
- Authentication, rate limiting, or multi-tenancy
- Inpainting, ControlNet, or variant workflows

## Capabilities

### New Capabilities
- `image-generation`: HTTP request acceptance, WebSocket job tracking, and Modal GPU execution of ComfyUI JSON workflows

### Modified Capabilities
- None

## Approach

1. **FastAPI ASGI**: Replace the stubbed `@modal.fastapi_endpoint` with a full FastAPI app served via `modal.asgi_app` so routes and WebSockets live in one container.
2. **CPU / GPU Split**: The API container runs on CPU. The generation task runs on GPU via `modal.function.spawn(...)` using a dedicated `@app.function` decorated job.
3. **WebSocket Tracking**: The client connects to the WS endpoint; the handler polls the Modal Call ID status and pushes updates to the client (stateless polling, no extra infrastructure).
4. **Feature-First Layout**: All generation logic is isolated under `src/features/generation/`. Shared Modal config and ComfyUI client utilities move to `src/shared/`.
5. **ComfyUI Integration**: The GPU function boots ComfyUI internally, posts the mutated JSON payload to `127.0.0.1:8188`, and waits for completion using the existing websocket logic.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/features/generation/` | New | Router, services, Pydantic models, Modal GPU job function |
| `src/shared/modal_config.py` | New | Shared Modal App and Image definitions |
| `src/shared/comfy_client.py` | New | Reusable ComfyUI HTTP + WS utilities |
| `app.py` | Modified | Switches from stub endpoint to `modal.asgi_app` mount |
| `api.py` | Modified | Refactored into `src/shared/comfy_client.py` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| GPU cold start > 30s | Med | Use Modal `keep_warm=1` during business hours; document expected latency |
| WebSocket polling overhead | Low | Poll interval 1s; Modal API calls are cheap; monitor connection count |
| ComfyUI JSON workflow fragility | Med | Lock `payload.json` version; validate required node IDs before enqueue |

## Rollback Plan

1. Revert `app.py` to the previous stubbed `@modal.fastapi_endpoint`.
2. Delete the `src/features/generation/` directory and `src/shared/` additions.
3. Restore `api.py` to its original synchronous WS client form.
4. No database or external state to migrate; rollback is pure code revert.

## Dependencies

- Active Modal account with GPU access (T4/A100)
- Valid ComfyUI JSON workflow exported in API format (`payload.json`)
- `modal` Python SDK installed in the deployment environment

## Success Criteria

- [ ] `POST /generate` with a prompt returns a unique `job_id` within 500ms
- [ ] `WS /ws/generate/{job_id}` connects and streams at least `queued`, `running`, `completed`, and `failed` states
- [ ] The GPU function successfully executes the ComfyUI workflow and produces an image file
- [ ] A complete end-to-end request (POST → WS → image) succeeds in a single integration test
