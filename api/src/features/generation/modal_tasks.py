import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from typing import Dict, Any, Optional

# Import shared Modal configuration
from src.shared.modal_config import modal_app, comfy_image, model_volume, image_volume, input_volume


def _load_graph_from_dict(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and return the resolved ComfyUI workflow graph.

    The graph is already resolved by the WorkflowEngine before being passed here.
    """
    if not graph or "prompt" not in graph:
        raise ValueError("Invalid workflow graph: missing 'prompt' key")
    return graph


def _boot_comfyui(port: int = 8188, comfyui_dir: str = "/root/ComfyUI") -> subprocess.Popen:
    """Start a headless ComfyUI server in its own process group.

    Returns the Popen handle so it can be terminated cleanly.
    """
    # Fix paths for custom nodes by symlinking cached models to expected ComfyUI locations
    os.makedirs(f"{comfyui_dir}/models/unet", exist_ok=True)
    os.makedirs(f"{comfyui_dir}/models/ultralytics/bbox", exist_ok=True)
    os.makedirs(f"{comfyui_dir}/models/onnx", exist_ok=True)

    if os.path.exists(f"{comfyui_dir}/models/face_detector"):
        for f in os.listdir(f"{comfyui_dir}/models/face_detector"):
            src = f"{comfyui_dir}/models/face_detector/{f}"
            dst1 = f"{comfyui_dir}/models/ultralytics/bbox/{f}"
            dst2 = f"{comfyui_dir}/models/onnx/{f}"
            if not os.path.exists(dst1):
                os.symlink(src, dst1)
            if not os.path.exists(dst2):
                os.symlink(src, dst2)

    cmd = [
        sys.executable,
        "main.py",
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    return subprocess.Popen(
        cmd,
        cwd=comfyui_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
        preexec_fn=os.setsid,
    )


def _shutdown_process_group(process: subprocess.Popen, term_wait_s: float = 10.0) -> None:
    """Terminate a ComfyUI process group gracefully, then forcefully.

    Sends SIGTERM to the process group, waits ``term_wait_s``, and sends
    SIGKILL if the process is still alive.
    """
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        process.wait(timeout=term_wait_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


_STREAM_END = object()


def _classify_comfyui_error(
    exception_message: str = "",
    exception_type: str | None = None,
    node_type: str | None = None,
) -> str:
    """Classify a ComfyUI execution error into a structured error code.

    Inspects the exception message, type, and node type to distinguish
    between node_missing (missing custom nodes), gpu_oom (VRAM pressure),
    no_face_detected (face detector failures), and generic failures.

    Returns one of: node_missing, gpu_oom, no_face_detected, comfyui_execution_failed.
    """
    combined = f"{exception_type or ''} {exception_message or ''} {node_type or ''}".lower()

    # Node missing: ComfyUI raises NodeNotFoundException or similar
    # when a custom node class is not installed/found
    if "node" in combined and ("not found" in combined or "not installed" in combined):
        return "node_missing"

    # GPU OOM: CUDA out-of-memory errors from torch/ComfyUI
    if "out of memory" in combined or ("cuda" in combined and "memory" in combined):
        return "gpu_oom"

    # No face detected: PuLID/face detector reports no valid face
    if "no face detected" in combined or "face not found" in combined:
        return "no_face_detected"

    return "comfyui_execution_failed"


def _next_event(gen):
    """Return the next event from a generator, or ``_STREAM_END`` on exhaustion."""
    try:
        return next(gen)
    except StopIteration:
        return _STREAM_END


async def _async_iter_stream_progress(client, prompt_id: str, deadline: float):
    """Asynchronously iterate over ``client.stream_progress`` with a hard deadline.

    Each step of the synchronous websocket iterator is run in a thread and
    wrapped with ``asyncio.wait_for`` so that a stuck ``recv()`` cannot block
    past the remaining pipeline budget.
    """
    loop = asyncio.get_event_loop()
    gen = client.stream_progress(prompt_id, deadline=deadline)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached")
        event = await asyncio.wait_for(
            loop.run_in_executor(None, _next_event, gen),
            timeout=remaining,
        )
        if event is _STREAM_END:
            break
        yield event


async def _execute_generation(
    job_id: str,
    graph: Dict[str, Any],
    store,
    client,
    pipeline_timeout_s: float = 300.0,
    term_wait_s: float = 10.0,
    output_artifacts: Optional[list[dict]] = None,
) -> None:
    """Run one ComfyUI generation job and update the job store along the way.

    This helper is separated from ``run_generation`` so it can be unit-tested
    without invoking Modal infrastructure. It is async so that blocking HTTP
    and WebSocket calls can be wrapped with ``asyncio.wait_for`` and a real
    hard deadline can be enforced.
    """
    process: Optional[subprocess.Popen] = None
    deadline = time.monotonic() + pipeline_timeout_s
    output_dir = "/root/ComfyUI/output"

    try:
        payload = _load_graph_from_dict(graph)
        await store.aupdate_job(
            job_id,
            status="booting_server",
            progress=0,
            message="Booting ComfyUI server",
        )
        process = _boot_comfyui()

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached during boot")
        await asyncio.wait_for(
            asyncio.to_thread(client.wait_ready, timeout_s=remaining),
            timeout=remaining,
        )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached during boot")
        await asyncio.wait_for(
            asyncio.to_thread(client.connect, timeout_s=remaining),
            timeout=remaining,
        )

        await store.aupdate_job(
            job_id,
            status="downloading_weights",
            progress=0,
            message="Validating cached weights",
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached before queueing prompt")
        prompt_id = await asyncio.wait_for(
            asyncio.to_thread(client.queue_prompt, payload, remaining),
            timeout=remaining,
        )

        await store.aupdate_job(
            job_id,
            status="generating",
            progress=0,
            message="Running ComfyUI inference",
        )
        async for event in _async_iter_stream_progress(client, prompt_id, deadline=deadline):
            event_type = event["event"]
            progress = event.get("progress")
            message = event.get("message")
            if event_type == "error":
                error_code = _classify_comfyui_error(
                    exception_message=message or "",
                    exception_type=event.get("exception_type"),
                    node_type=event.get("node_type"),
                )
                await store.aupdate_job(
                    job_id,
                    status="error",
                    error_code=error_code,
                    error_detail=message or "ComfyUI execution failed",
                )
                return
            await store.aupdate_job(
                job_id,
                status=event_type,
                progress=progress,
                message=message,
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached before output retrieval")
        image_path = await asyncio.wait_for(
            asyncio.to_thread(client.resolve_output_path, prompt_id, output_dir, remaining),
            timeout=remaining,
        )
        
        # IMPORTANTE: Persistimos el volumen ANTES de avisarle al cliente por WS.
        # Esto evita la "Race Condition" donde el cliente hace el GET /images antes de que Modal sincronice.
        from src.shared.modal_config import image_volume
        try:
            await asyncio.to_thread(image_volume.commit)
        except Exception:
            pass

        # Build artifacts array from manifest output artifact config
        artifacts: Optional[list[dict]] = None
        if output_artifacts:
            artifacts = []
            for art_cfg in output_artifacts:
                artifacts.append({
                    "name": art_cfg.get("name", "artifact"),
                    "volume_path": image_path,
                    "media_type": art_cfg.get("media_type", "image/png"),
                    "source_job_id": job_id,
                })

        await store.aupdate_job(
            job_id,
            status="completed",
            image_path=image_path,
            progress=100,
            message="Finished",
            artifacts=artifacts,
        )
    except TimeoutError:
        await store.aupdate_job(
            job_id,
            status="error",
            error_code="timeout",
            error_detail=f"Generation exceeded {pipeline_timeout_s}s deadline",
        )
    except Exception as exc:
        await store.aupdate_job(
            job_id,
            status="error",
            error_code="comfyui_execution_failed",
            error_detail=str(exc),
        )
    finally:
        if process is not None:
            _shutdown_process_group(process, term_wait_s=term_wait_s)
        await asyncio.to_thread(client.close)


def _run_generation_impl(
    job_id: str,
    graph: Dict[str, Any],
    output_artifacts: Optional[list[dict]] = None,
    pipeline_timeout_s: float = 1180.0,
) -> str:
    from src.shared.job_store import JobStore
    from src.shared.comfy_client import ComfyUIClient

    store = JobStore()
    client = ComfyUIClient("127.0.0.1:8188")
    asyncio.run(_execute_generation(
        job_id, graph, store, client,
        pipeline_timeout_s=pipeline_timeout_s,
        output_artifacts=output_artifacts,
    ))

    job = store.get_job(job_id)
    if job is None:
        raise RuntimeError(f"Job {job_id} disappeared during generation")
    if job["status"] == "error":
        raise RuntimeError(f"Generation failed: {job['error_code']} - {job['error_detail']}")
    
    return job["image_path"]

@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    gpu="T4",
    timeout=1200,
)
def run_generation(
    job_id: str,
    graph: Dict[str, Any],
    output_artifacts: Optional[list[dict]] = None,
) -> str:
    """Modal background function to execute standard ComfyUI GPU workflows on T4."""
    return _run_generation_impl(job_id, graph, output_artifacts=output_artifacts)

@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    gpu="L4",
    timeout=1800,
)
def run_generation_heavy(
    job_id: str,
    graph: Dict[str, Any],
    output_artifacts: Optional[list[dict]] = None,
    pipeline_timeout_s: float = 1780.0,
) -> str:
    """Modal background function to execute heavy ComfyUI GPU workflows on L4.

    Args:
        job_id: The job identifier.
        graph: Resolved ComfyUI workflow graph.
        output_artifacts: Optional manifest output artifact configs.
        pipeline_timeout_s: Internal ComfyUI pipeline deadline.
            Flow-level timeout (e.g. 600s for composition) is forwarded
            by dispatch_flow to respect the flow's SLO.
    """
    from src.shared.job_store import JobStore
    from src.shared.comfy_client import ComfyUIClient

    store = JobStore()
    client = ComfyUIClient("127.0.0.1:8188")
    asyncio.run(_execute_generation(
        job_id, graph, store, client,
        pipeline_timeout_s=pipeline_timeout_s,
        output_artifacts=output_artifacts,
    ))

    job = store.get_job(job_id)
    if job is None:
        raise RuntimeError(f"Job {job_id} disappeared during generation")
    if job["status"] == "error":
        raise RuntimeError(f"Generation failed: {job['error_code']} - {job['error_detail']}")
    
    return job["image_path"]


@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    gpu="A100",
    timeout=3600,
)
def run_generation_a100(
    job_id: str,
    graph: Dict[str, Any],
    output_artifacts: Optional[list[dict]] = None,
    pipeline_timeout_s: float = 3580.0,
) -> str:
    """Modal background function to execute identity preservation workflows on A100.

    Args:
        job_id: The job identifier.
        graph: Resolved ComfyUI workflow graph.
        output_artifacts: Optional manifest output artifact configs.
        pipeline_timeout_s: Internal ComfyUI pipeline deadline.
            Flow-level timeout (e.g. 1200s for identity) is forwarded
            by dispatch_flow to respect the flow's SLO.
    """
    from src.shared.job_store import JobStore
    from src.shared.comfy_client import ComfyUIClient

    store = JobStore()
    client = ComfyUIClient("127.0.0.1:8188")
    asyncio.run(_execute_generation(
        job_id, graph, store, client,
        pipeline_timeout_s=pipeline_timeout_s,
        output_artifacts=output_artifacts,
    ))

    job = store.get_job(job_id)
    if job is None:
        raise RuntimeError(f"Job {job_id} disappeared during generation")
    if job["status"] == "error":
        raise RuntimeError(f"Generation failed: {job['error_code']} - {job['error_detail']}")
    
    return job["image_path"]
