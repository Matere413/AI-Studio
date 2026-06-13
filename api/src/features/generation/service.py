import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Generator
from src.shared.job_store import JobStore
from src.shared.workflows.engine import WorkflowEngine
from src.features.generation.models import JobEvent, JobEventResult, JobEventError


class GenerationService:
    """Business logic for generation job lifecycle management.

    Contract: create jobs, resolve workflows, enqueue Modal work, and map failures to terminal errors.
    """

    def __init__(self, job_store: JobStore):
        self._store = job_store

    def create_job(self, prompt: str) -> str:
        """Create a new generation job.

        Validates the prompt and stores the job with pending status.
        Returns the unique job_id.
        """
        if not prompt or len(prompt.strip()) == 0:
            raise ValueError("Prompt cannot be empty")
        return self._store.create_job(prompt)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by job_id.

        Returns None if the job does not exist.
        """
        return self._store.get_job(job_id)

    def map_failure_to_error(self, code: str, detail: str) -> Dict[str, str]:
        """Map a failure to a terminal error structure.

        Returns a dict with error code and detail.
        """
        return {"code": code, "detail": detail}

    def resolve_workflow(self, workflow_name: str = "txt2img", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve a workflow template with runtime parameters.

        Args:
            workflow_name: Name of the workflow directory under src/workflows/.
            params: Runtime parameters to inject into the template.

        Returns:
            The resolved ComfyUI workflow graph dict.

        Raises:
            ValueError: If the workflow template or manifest is missing.
        """
        src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        base_dir = os.path.join(src_root, "workflows", workflow_name)
        template_path = os.path.join(base_dir, "workflow.json")
        manifest_path = os.path.join(base_dir, "manifest.yaml")

        engine = WorkflowEngine(template_path, manifest_path)
        return engine.execute(params or {})

    def enqueue_modal_work(
        self,
        job_id: str,
        prompt: str,
        workflow_name: str = "txt2img",
        checkpoint_url: Optional[str] = None,
        lora_url: Optional[str] = None,
        image_url: Optional[str] = None,
        control_image_url: Optional[str] = None,
        control_strength: Optional[float] = None,
        denoise: Optional[float] = None,
    ) -> None:
        """Enqueue Modal work for a job.

        Resolves the workflow with parameters, triggers model caching if needed,
        and spawns the background generation task.
        Raises ValueError if a parameter is not declared by the workflow manifest.
        """
        params = {"prompt": prompt}
        if checkpoint_url:
            filename = os.path.basename(checkpoint_url)
            from src.shared.workflows.cache import download_model
            download_model.spawn(checkpoint_url, filename)
            params["checkpoint"] = filename
        if lora_url:
            params["lora"] = lora_url
        if image_url:
            params["image_url"] = image_url
        if control_image_url:
            params["control_image_url"] = control_image_url
        if control_strength is not None:
            params["control_strength"] = control_strength
        if denoise is not None:
            params["denoise"] = denoise

        # Validate params against the manifest before resolving
        # Get absolute path to the workflows directory
        src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        base_dir = os.path.join(src_root, "workflows", workflow_name)
        template_path = os.path.join(base_dir, "workflow.json")
        manifest_path = os.path.join(base_dir, "manifest.yaml")
        engine = WorkflowEngine(template_path, manifest_path)

        for key in params:
            if key not in engine.manifest.inputs:
                raise ValueError(
                    f"Parameter '{key}' is not supported by workflow '{workflow_name}'"
                )

        resolved_graph = engine.execute(params)

        from src.features.generation.modal_tasks import run_generation
        run_generation.spawn(job_id, resolved_graph)

    def _build_event(self, job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """Build a JobEvent-compatible dict from job state."""
        event_type = job["status"]
        event = {
            "event": event_type,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if event_type == "completed":
            event["result"] = {"image_path": job["image_path"]}
        elif event_type == "error":
            event["error"] = {"code": job["error_code"], "detail": job["error_detail"]}
        else:
            # pending or running
            event["progress"] = 0 if event_type == "pending" else 50
            event["message"] = "Job queued" if event_type == "pending" else "Processing"

        return event

    def get_job_events(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Yield lifecycle events for a job.

        Returns the current known state as a JobEvent-compatible dict.
        """
        job = self._store.get_job(job_id)
        if job is None:
            yield {
                "event": "error",
                "job_id": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": {"code": "NOT_FOUND", "detail": "Job does not exist"},
            }
            return

        yield self._build_event(job_id, job)

    async def poll_job_events(self, job_id: str, interval: float = 0.5):
        """Async generator that polls job state and yields events until terminal.

        Yields a JobEvent-compatible dict each time the job state changes.
        Stops when the job reaches a terminal state (completed or error).
        """
        import asyncio
        last_status = None
        while True:
            job = self._store.get_job(job_id)
            if job is None:
                yield {
                    "event": "error",
                    "job_id": job_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": {"code": "NOT_FOUND", "detail": "Job does not exist"},
                }
                return

            current_status = job["status"]
            if current_status != last_status:
                yield self._build_event(job_id, job)
                last_status = current_status

            if current_status in ["completed", "error"]:
                return

            await asyncio.sleep(interval)
