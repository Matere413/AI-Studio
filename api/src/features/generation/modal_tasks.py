import json
import os
import signal
import subprocess
import sys
import time
from typing import Dict, Any, Optional

# Import shared Modal configuration
from src.shared.modal_config import modal_app, comfy_image, model_volume, image_volume


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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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


def _execute_generation(
    job_id: str,
    graph: Dict[str, Any],
    store,
    client,
    pipeline_timeout_s: float = 300.0,
    term_wait_s: float = 10.0,
) -> None:
    """Run one ComfyUI generation job and update the job store along the way.

    This helper is separated from ``run_generation`` so it can be unit-tested
    without invoking Modal infrastructure.
    """
    process: Optional[subprocess.Popen] = None
    deadline = time.monotonic() + pipeline_timeout_s
    output_dir = "/root/ComfyUI/output"

    try:
        payload = _load_graph_from_dict(graph)
        store.update_job(
            job_id,
            status="booting_server",
            progress=0,
            message="Booting ComfyUI server",
        )
        process = _boot_comfyui()

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Generation deadline reached during boot")
        client.wait_ready(timeout_s=remaining)

        store.update_job(
            job_id,
            status="downloading_weights",
            progress=0,
            message="Validating cached weights",
        )
        prompt_id = client.queue_prompt(payload)

        store.update_job(
            job_id,
            status="generating",
            progress=0,
            message="Running ComfyUI inference",
        )
        for event in client.stream_progress(prompt_id, deadline=deadline):
            event_type = event["event"]
            progress = event.get("progress")
            message = event.get("message")
            if event_type == "error":
                store.update_job(
                    job_id,
                    status="error",
                    error_code="comfyui_execution_failed",
                    error_detail=message or "ComfyUI execution failed",
                )
                return
            store.update_job(
                job_id,
                status=event_type,
                progress=progress,
                message=message,
            )

        image_path = client.resolve_output_path(prompt_id, output_dir)
        store.update_job(
            job_id,
            status="completed",
            image_path=image_path,
            progress=100,
            message="Finished",
        )
    except TimeoutError:
        store.update_job(
            job_id,
            status="error",
            error_code="timeout",
            error_detail="Generation exceeded 300s deadline",
        )
    except Exception as exc:
        store.update_job(
            job_id,
            status="error",
            error_code="comfyui_execution_failed",
            error_detail=str(exc),
        )
    finally:
        if process is not None:
            _shutdown_process_group(process, term_wait_s=term_wait_s)


@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
    },
    gpu="T4",
)
def run_generation(job_id: str, graph: Dict[str, Any]) -> str:
    """Modal background function to execute the ComfyUI GPU workflow.

    Accepts a pre-resolved workflow graph (from WorkflowEngine) and executes it.
    Returns the image path or raises on failure.
    """
    from src.shared.job_store import JobStore
    from src.shared.comfy_client import ComfyUIClient

    store = JobStore()
    client = ComfyUIClient("127.0.0.1:8188")
    _execute_generation(job_id, graph, store, client)

    job = store.get_job(job_id)
    if job is None:
        raise RuntimeError(f"Job {job_id} disappeared during generation")
    if job["status"] == "error":
        raise RuntimeError(f"Generation failed: {job['error_code']} - {job['error_detail']}")
    return job["image_path"]
