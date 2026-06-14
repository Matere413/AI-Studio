# Design: ComfyUI Real Integration

## Technical Approach

Replace the `picsum.photos` stub with a Modal GPU execution path that starts a local headless ComfyUI process per generation job, dispatches the resolved JSON graph via localhost HTTP, tracks ComfyUI WebSocket progress into `JobStore`, and stores final images in a Modal Volume served by FastAPI. Strict TDD applies before implementation.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| ComfyUI lifecycle | Spawn ComfyUI inside `run_generation` with `subprocess.Popen(..., cwd="/root/ComfyUI", preexec_fn=os.setsid)` and always clean up in `finally`. | Always-warm Modal service. | Matches V1 scope and prevents orphan GPU processes after timeout/error. |
| Readiness | Poll `GET http://127.0.0.1:8188/system_stats` every 0.5s until ready or boot deadline. | Blind sleep. | Deterministic tests and faster failures. |
| Timeout cleanup | Enforce one 300s deadline around boot + inference; on breach set `error.timeout`, then `SIGTERM` process group, wait 10s, `SIGKILL` if still alive. | Let Modal timeout kill container. | Explicit terminal job state and lower GPU OOM/leak risk. |
| Progress relay | ComfyUI task writes granular status/progress to Modal `JobStore`; FastAPI WS keeps polling current state. | Direct socket bridge from Modal task to client. | Fits current reconnect semantics and avoids cross-container WS coupling. |
| Image storage | Add `image_volume` mounted at `/root/ComfyUI/output` in both ASGI and generation functions. | Return base64 or remote object storage. | Satisfies V1 “no object storage” and serves bytes directly. |
| Model policy | Validate whitelist in `GenerationService` before `run_generation.spawn`; validate cache presence in `cache.py` without runtime downloads. | Download missing whitelisted models. | Enforces spec boundary and avoids untrusted runtime fetches. |

## Data Flow

```text
POST /generate
  -> GenerationService.validate_models()
  -> WorkflowEngine.execute()
  -> run_generation.spawn(job_id, graph)

run_generation
  -> JobStore: booting_server
  -> Popen ComfyUI localhost:8188
  -> healthcheck /system_stats
  -> JobStore: downloading_weights (cache validation only)
  -> ComfyUIClient.send_prompt() HTTP /prompt
  -> ComfyUIClient.stream_events() WS /ws
  -> JobStore: generating/progress/completed|error
  -> finally terminate process group

WS /ws/generate/{job_id} -> poll JobStore -> client
GET /images/{job_id} -> JobStore.image_path -> Modal Volume bytes
```

## File Changes

| File | Action | Description |
|---|---|---|
| `api/src/shared/modal_config.py` | Modify | Add `image_volume`, install `requests`, mount outputs alongside models. |
| `api/src/features/generation/modal_tasks.py` | Modify | Implement ComfyUI subprocess boot, readiness polling, timeout deadline, ComfyUI execution, output discovery, SIGTERM/SIGKILL cleanup. |
| `api/src/shared/comfy_client.py` | Modify | Return `prompt_id`, parse WS `progress`, `executing`, `executed`, `execution_error`, and resolve output filenames/history. |
| `api/src/features/generation/service.py` | Modify | Enforce whitelist before spawn, map `model_not_allowed`, keep routers thin, emit new event names. |
| `api/src/features/generation/router.py` | Modify | Add `GET /images/{job_id}` with `FileResponse`/JSON 404 errors. |
| `api/src/features/generation/models.py` | Modify | Update `JobEvent.event` enum and error codes; support `checkpoint`/`lora` identifiers while preserving existing request compatibility if needed. |
| `api/src/shared/job_store.py` | Modify | Store `progress`, `message`, `image_path`, terminal error detail. |
| `api/src/shared/workflows/cache.py` | Modify | Replace download-on-miss with whitelist/config loading and cached-path checks. |
| `api/src/tests/*` | Modify/Add | TDD for subprocess cleanup, progress parsing, whitelist rejection, image serving, timeout. |

## Interfaces / Contracts

```python
class ComfyUIClient:
    def wait_ready(self, timeout_s: float) -> None: ...
    def queue_prompt(self, payload: dict) -> str: ...  # returns prompt_id
    def stream_progress(self, prompt_id: str, deadline: float): ...
    def resolve_output_path(self, prompt_id: str, output_dir: str) -> str: ...
```

Whitelist config: `ALLOWED_MODELS_JSON='{"checkpoints":["sdxl.safetensors"],"loras":[]}'`. Cache paths remain under `/root/ComfyUI/models/{checkpoints|loras}/`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Client WS parsing, whitelist/cache checks, process cleanup. | Mock `websocket`, `urllib`, `subprocess.Popen`, `os.killpg`. |
| Integration | `POST /generate` rejects unknown models before spawn; `GET /images/{job_id}` returns bytes/404 codes. | FastAPI `TestClient`, patched Modal functions and temp files. |
| E2E | WS lifecycle emits booting/download/generating/progress/completed/error. | Existing websocket tests with controlled `JobStore` transitions. |

## Migration / Rollout

No data migration required. Deploy behind the existing API contract; rollback restores mock `run_generation` and removes image serving.

## Open Questions

- [ ] Confirm exact whitelisted model identifiers and Volume directory layout for checkpoints/LoRAs.
