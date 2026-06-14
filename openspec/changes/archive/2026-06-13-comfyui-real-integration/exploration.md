# Exploration: Real ComfyUI Backend Integration

## Current State
The generation pipeline currently uses a **mock/stub** in `api/src/features/generation/modal_tasks.py`. The `run_generation` Modal function sleeps for 3 seconds and returns a fake placeholder image URL (`https://picsum.photos/seed/{job_id}/512/512`). There is a TODO comment indicating this will be replaced with real ComfyUI execution.

The rest of the infrastructure is already well-architected and ready:
- **WorkflowEngine** (`api/src/shared/workflows/engine.py`) resolves JSON graph templates with runtime parameters via YAML manifests.
- **ComfyUIClient** (`api/src/shared/comfy_client.py`) already exists with WebSocket connect, HTTP prompt dispatch, and completion listening.
- **JobStore** (`api/src/shared/job_store.py`) uses `modal.Dict` for distributed state across containers.
- **GenerationService** (`api/src/features/generation/service.py`) orchestrates job creation, workflow resolution, Modal task spawning, and event polling.
- **Modal Image** (`api/src/shared/modal_config.py`) clones ComfyUI into the container and installs dependencies (`websocket-client`, `fastapi`).
- **Model caching** (`api/src/shared/workflows/cache.py`) downloads `.safetensors` into a Modal Volume.
- **WebSocket endpoint** (`api/src/features/generation/router.py`) streams lifecycle events to clients.

## Affected Areas
- `api/src/features/generation/modal_tasks.py` — **Core change**: replace the mock sleep + fake URL with real ComfyUI server startup, graph execution, and result retrieval.
- `api/src/shared/comfy_client.py` — **Enhancement needed**: add progress event parsing (`progress` WebSocket messages) and update the JobStore with progress updates. Also needs to handle output image retrieval (from ComfyUI output folder or API).
- `api/src/features/generation/service.py` — **Minor changes**: possibly adjust `enqueue_modal_work` to pass additional metadata needed by the real client (e.g., output filename prefix).
- `api/src/tests/test_modal_tasks.py` — **Tests must be updated**: current tests assert the function is a Modal Function and has correct signature. Real execution will require mocking the ComfyUI server or using a test container.
- `api/src/tests/test_generation_service.py` — **Tests must be updated**: currently mocks `run_generation.spawn`. Real execution means the mock should simulate a more realistic flow, or tests should focus on the client layer.
- `api/src/tests/test_comfy_client.py` — **Tests should be expanded**: to cover progress parsing and error handling paths.
- `api/src/shared/modal_config.py` — **Possible enhancement**: add `comfyui` startup command or ensure the server is available inside the Modal container.

## Approaches

### 1. In-Process ComfyUI Execution (WebSocket + HTTP)
**Description**: Inside the Modal `run_generation` task, start the ComfyUI server in a background thread/subprocess, connect via `ComfyUIClient` (WebSocket + HTTP), send the resolved graph, listen for completion, and read the generated image from the output folder.

- **Pros**:
  - Simple and direct; reuses existing `ComfyUIClient`.
  - No external network calls needed inside the container.
  - Full control over the ComfyUI process lifecycle.
- **Cons**:
  - ComfyUI server startup time adds latency to every generation task.
  - Must manage the subprocess lifecycle (kill, restart, health checks).
  - GPU memory fragmentation risk if the server process is not cleaned up properly.
  - Modal task timeout may be hit if server startup + inference is long.
- **Effort**: Medium

### 2. Headless ComfyUI API Mode (HTTP Polling)
**Description**: Start ComfyUI in `--listen` + API mode inside the Modal image (or as a separate long-running Modal service). Use HTTP only: POST to `/prompt`, poll `/history/{prompt_id}` until completion, then fetch the image via `/view` or read from disk.

- **Pros**:
  - Simpler than WebSocket lifecycle management.
  - Easier to test and debug with `curl`.
  - No need to keep a WebSocket connection alive.
- **Cons**:
  - Loses real-time progress updates (no `progress` messages).
  - Polling adds latency and unnecessary HTTP requests.
  - The existing `ComfyUIClient` is WebSocket-based; would need a new HTTP-only client.
- **Effort**: Medium

### 3. Separate ComfyUI Service + Modal Task Calls
**Description**: Run ComfyUI as a separate Modal service (long-running GPU container) with a stable endpoint. The `run_generation` task calls this service via HTTP/WebSocket.

- **Pros**:
  - Best separation of concerns; FastAPI layer and ComfyUI are decoupled.
  - ComfyUI server is always warm; no startup overhead per generation.
  - Can scale ComfyUI independently from the API layer.
- **Cons**:
  - More complex Modal infrastructure (two services, networking, service discovery).
  - Overkill for the current MVP scope.
  - Adds cross-container network latency.
- **Effort**: High

### 4. Hybrid: ComfyUIClient + WebSocket Progress + Direct File Read
**Description**: Enhance the existing `ComfyUIClient` to parse `progress` messages and update `JobStore` in real-time. In `run_generation`, start ComfyUI server (or ensure it is running), use `ComfyUIClient` to send and wait, then read the output image directly from `/root/ComfyUI/output/` and upload to S3/R2 (or return a Modal Volume path). This is the most natural evolution from the current code.

- **Pros**:
  - Reuses all existing infrastructure (client, job store, workflow engine).
  - Provides real-time progress updates to the WebSocket frontend.
  - Direct file access is fast and reliable inside the container.
  - Aligns with the existing TODO comment in `modal_tasks.py`.
- **Cons**:
  - Requires modifying `ComfyUIClient` to handle progress and error states robustly.
  - Need to handle ComfyUI server startup inside the Modal task.
  - Need to decide on image persistence strategy (S3 vs Modal Volume vs base64).
- **Effort**: Medium

## Recommendation
**Approach 4: Hybrid ComfyUIClient + WebSocket Progress + Direct File Read**

This is the most pragmatic evolution from the current codebase. It maximizes reuse of existing code (`ComfyUIClient`, `JobStore`, `WorkflowEngine`) and provides the best user experience (real-time progress). The key implementation steps are:

1. **Enhance `ComfyUIClient`**: Add `track_progress` method that listens for `progress` messages and calls a callback to update `JobStore`. Also add `get_image_path(output)` helper.
2. **Modify `run_generation`**: Replace `time.sleep(3)` with:
   - Start ComfyUI server in the background (if not already running) or ensure it is running.
   - Instantiate `ComfyUIClient(server_address="127.0.0.1:8188")`.
   - Connect, send the resolved graph, and listen for completion while updating progress.
   - Read the generated image from the output directory.
   - Update the job store with the real image path (or a Modal Volume / S3 URL).
3. **Handle errors**: Wrap ComfyUI connection/execution errors and map them to terminal job states.
4. **Tests**: Keep `test_generation_service.py` mocking the Modal task, but expand `test_comfy_client.py` to test progress parsing. Add integration tests for `run_generation` with a mocked ComfyUI server subprocess.

## Risks
- **ComfyUI server startup latency**: Starting ComfyUI inside every Modal task may add 10-30 seconds. Mitigation: keep it warm or use a long-running Modal service.
- **GPU OOM / process cleanup**: If the ComfyUI subprocess is not killed after inference, subsequent tasks may fail. Mitigation: explicit subprocess management and health checks.
- **Image persistence**: Currently the mock returns a URL. Real images are local files. Need to decide on S3/R2 upload or Modal Volume exposure before the frontend can display them.
- **WebSocket reliability**: Inside a Modal container, WebSocket connections to localhost should be reliable, but network timeouts must be handled.
- **Breaking existing tests**: The E2E tests and service tests rely on mocking `run_generation`. Changing its behavior will not break them immediately (since they mock it), but the mock should be updated to reflect real signatures if new parameters are added.
- **Model availability**: Real ComfyUI requires the checkpoint to be present in the Modal Volume. If the model is missing, the job will fail. The existing `download_model` caching should handle this, but we need to ensure the download completes before the workflow runs.

## Ready for Proposal
**Yes.** The exploration confirms the codebase is well-structured for this change. The mock is isolated in `modal_tasks.py`, and the surrounding infrastructure (client, job store, workflow engine) is ready. The next step is to write the `proposal.md` with the exact scope, rollback plan, and acceptance criteria.

**What the orchestrator should tell the user**: The mock is cleanly isolated and the real integration path is clear. The main decision needed is how to handle image persistence (S3/R2 vs Modal Volume) and whether to accept the ComfyUI server startup latency per task or move to a warm service later. I recommend proceeding to the Proposal phase.
