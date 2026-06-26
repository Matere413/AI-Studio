import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from typing import Dict, Any, Optional

import boto3
import botocore

from src.shared.logging import get_logger

_log = get_logger(__name__)

# Import shared Modal configuration
from src.shared.modal_config import (
    modal_app,
    comfy_image,
    model_volume,
    image_volume,
    input_volume,
    r2_secret,
)


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


def _upload_to_r2(file_path: str, key: str) -> str:
    """Upload a file to Cloudflare R2 and return a presigned GET URL.

    Reads R2 credentials from environment variables (injected by the
    ``r2-secret`` Modal Secret).  The key is prefixed with ``generated/``
    to namespace generation outputs separately from user-uploaded assets.

    Args:
        file_path: Absolute path to the local file to upload.
        key: Object key (without the ``generated/`` prefix).

    Returns:
        A presigned GET URL valid for 1 hour.
    """
    endpoint = os.environ.get("R2_ENDPOINT")
    access_key = os.environ.get("R2_ACCESS_KEY")
    secret_key = os.environ.get("R2_SECRET_KEY")
    bucket = os.environ.get("R2_BUCKET")

    if not all([endpoint, access_key, secret_key, bucket]):
        _log.warning(
            "r2_not_configured",
            has_endpoint=bool(endpoint),
            has_access_key=bool(access_key),
            has_secret_key=bool(secret_key),
            has_bucket=bool(bucket),
        )
        raise RuntimeError("R2 storage is not configured — missing environment variables")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=botocore.config.Config(
            connect_timeout=5,
            read_timeout=10,
            retries={"max_attempts": 3},
        ),
    )

    r2_key = f"generated/{key}"
    with open(file_path, "rb") as f:
        client.upload_fileobj(
            f, bucket, r2_key,
            ExtraArgs={"ContentType": "image/webp"},
        )

    presigned_url = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": r2_key},
        ExpiresIn=3600,
    )
    _log.info("r2_upload_complete", r2_key=r2_key)
    return presigned_url


def _init_sentry() -> None:
    """Initialise Sentry SDK inside Modal worker context if SENTRY_DSN is set.

    Modal workers run in separate containers from the FastAPI app, so they
    need their own sentry_sdk.init() call.  Safe to call redundantly —
    sentry_sdk.init() is idempotent within a process.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=dsn)
        except Exception:
            pass  # sentry-sdk not installed


_STREAM_END = object()


def _capture_sentry(
    job_id: str,
    error_code: str,
    exception: BaseException | None = None,
) -> None:
    """Capture an exception in Sentry if the SDK is initialised.

    Safe to call when Sentry is not configured — no-op in that case.
    Calls ``sentry_sdk.flush()`` after capturing so the event is sent before
    the Modal worker container is terminated.
    """
    try:
        import sentry_sdk

        if sentry_sdk.is_initialized():
            with sentry_sdk.new_scope() as scope:
                scope.set_tag("job_id", job_id)
                scope.set_tag("error_code", error_code)
                if exception:
                    sentry_sdk.capture_exception(exception)
                else:
                    sentry_sdk.capture_message(
                        f"Generation {error_code} for job {job_id}",
                        level="error",
                    )
            sentry_sdk.flush()
    except Exception:
        pass  # sentry-sdk not installed or not configured — no-op


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
    output_is_webp: bool = False

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
                # Capture ComfyUI runtime errors in Sentry before returning
                _capture_sentry(job_id, error_code)
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

        # Convert ComfyUI output (PNG) to WebP@90% for storage efficiency.
        # The SaveImage node in ComfyUI always saves as PNG; we convert to
        # WebP after output resolution so the stored artifact is smaller.
        try:
            webp_path = image_path.rsplit(".", 1)[0] + ".webp"
            from PIL import Image as PILImage
            img = PILImage.open(image_path)
            img.save(webp_path, format="webp", quality=90)
            # Replace the original image_path with the WebP variant
            image_path = webp_path
            output_is_webp = True
        except Exception:
            pass  # Fall back to original format if conversion fails

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
                media_type = art_cfg.get("media_type", "image/png")
                # Override media_type to image/webp when conversion succeeded
                if output_is_webp:
                    media_type = "image/webp"
                artifacts.append({
                    "name": art_cfg.get("name", "artifact"),
                    "volume_path": image_path,
                    "media_type": media_type,
                    "source_job_id": job_id,
                })

        # Upload the generated WebP to Cloudflare R2 for persistent storage.
        # The upload is wrapped in asyncio.wait_for against the remaining
        # pipeline budget so a stuck R2 client cannot exceed pipeline_timeout_s
        # (R4 fix: previously the upload ran OUTSIDE the budget block).
        # Failures are non-fatal (fall back to volume-based image serving)
        # but ARE observable — logged at error level with exc_info and
        # captured in Sentry (R4 fix: previously a silent warning).
        r2_url: str | None = None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _log.warning(
                "generation_r2_upload_skipped_no_budget",
                job_id=job_id,
            )
        else:
            try:
                r2_url = await asyncio.wait_for(
                    asyncio.to_thread(_upload_to_r2, image_path, f"{job_id}/output.webp"),
                    timeout=remaining,
                )
                _log.info("generation_r2_uploaded", job_id=job_id)
            except Exception as exc:
                _log.error(
                    "generation_r2_upload_failed",
                    job_id=job_id,
                    error=str(exc)[:200],
                    exc_info=True,
                )
                _capture_sentry(job_id, "r2_upload_failed", exception=exc)
                # Non-fatal: fall back to volume-based image serving

        await store.aupdate_job(
            job_id,
            status="completed",
            image_path=image_path,
            r2_url=r2_url,
            progress=100,
            message="Finished",
            artifacts=artifacts,
        )
    except TimeoutError:
        _log.error("generation_timeout", job_id=job_id, pipeline_timeout_s=pipeline_timeout_s)
        await store.aupdate_job(
            job_id,
            status="error",
            error_code="timeout",
            error_detail=f"Generation exceeded {pipeline_timeout_s}s deadline",
        )
        # Capture timeout in Sentry when DSN is configured
        _capture_sentry(job_id, "generation_timeout")
    except Exception as exc:
        _log.error(
            "generation_failed",
            job_id=job_id,
            error=str(exc)[:500],
        )
        await store.aupdate_job(
            job_id,
            status="error",
            error_code="comfyui_execution_failed",
            error_detail=str(exc),
        )
        _capture_sentry(job_id, "generation_failed", exception=exc)
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
    
    # Return R2 URL when available, fall back to local image_path
    return job.get("r2_url") or job["image_path"]


@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    secrets=[r2_secret],
    gpu="T4",
    timeout=1200,
)
def run_generation(
    job_id: str,
    graph: Dict[str, Any],
    output_artifacts: Optional[list[dict]] = None,
) -> str:
    """Modal background function to execute standard ComfyUI GPU workflows on T4."""
    _init_sentry()
    return _run_generation_impl(job_id, graph, output_artifacts=output_artifacts)

@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    secrets=[r2_secret],
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
    _init_sentry()
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
    
    # Return R2 URL when available, fall back to local image_path
    return job.get("r2_url") or job["image_path"]


@modal_app.function(
    image=comfy_image,
    volumes={
        "/root/ComfyUI/models": model_volume,
        "/root/ComfyUI/output": image_volume,
        "/root/ComfyUI/input": input_volume,
    },
    secrets=[r2_secret],
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
    _init_sentry()
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
    
    # Return R2 URL when available, fall back to local image_path
    return job.get("r2_url") or job["image_path"]
