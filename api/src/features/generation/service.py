import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Generator
from src.shared.job_store import JobStore
from src.shared.workflows.engine import WorkflowEngine
from src.shared.workflows.cache import load_whitelist, resolve_cached_model, ModelNotCachedError
from src.features.generation.models import JobEvent, JobEventResult, JobEventError


LOCKED_MODEL_WORKFLOWS = {"product_premium", "realistic_persona"}
QWEN_WORKFLOW = "qwen_txt2img"
QWEN_LIGHTNING_LORA = "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors"
QWEN_QUALITY_DEFAULTS = {
    "high": {
        "steps": 50,
        "cfg": 7.0,
        "sampler_name": "euler_ancestral",
        "sampler_scheduler": "normal",
    },
    "fast": {
        "steps": 4,
        "cfg": 1.5,
        "sampler_name": "euler",
        "sampler_scheduler": "sgm_uniform",
    },
}
MODEL_TYPE_BY_SEMANTIC_NAME = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "unet": "unets",
    "clip": "clip",
    "vae": "vae",
}
PERSONA_PARAM_NAMES = (
    "age",
    "gender",
    "ethnicity",
    "wardrobe",
    "expression",
    "background",
    "output_type",
)


def resolve_qwen_quality_defaults(quality_mode: str) -> Dict[str, Any]:
    """Resolve Qwen sampler defaults for the requested speed/quality mode."""
    try:
        return dict(QWEN_QUALITY_DEFAULTS[quality_mode])
    except KeyError as exc:
        raise ValueError("quality_mode must be 'fast' or 'high'") from exc


def inject_qwen_lightning_lora(
    graph: Dict[str, Any],
    lora_name: str = QWEN_LIGHTNING_LORA,
    sampler_node_id: str = "6",
) -> Dict[str, Any]:
    """Insert a Lightning LoRA node before Qwen KSampler and redirect model input."""
    prompt_nodes = graph["prompt"]
    sampler_inputs = prompt_nodes[sampler_node_id]["inputs"]
    original_model = sampler_inputs["model"]
    numeric_node_ids = [int(node_id) for node_id in prompt_nodes if node_id.isdigit()]
    lora_node_id = str(max(numeric_node_ids, default=0) + 1)

    prompt_nodes[lora_node_id] = {
        "inputs": {
            "model": original_model,
            "lora_name": lora_name,
            "strength_model": 1.0,
        },
        "class_type": "LoraLoaderModelOnly",
        "_meta": {"title": "Qwen Lightning LoRA"},
    }
    sampler_inputs["model"] = [lora_node_id, 0]
    return graph


class ModelNotAllowedError(ValueError):
    """Raised when a requested model is not in the allowed whitelist."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(
            f"model_not_allowed: Model '{model_id}' is not in the allowed whitelist."
        )


class GenerationService:
    """Business logic for generation job lifecycle management.

    Contract: create jobs, resolve workflows, enqueue Modal work, and map failures to terminal errors.
    """

    def __init__(self, job_store: JobStore):
        self._store = job_store

    def validate_models(
        self,
        checkpoint: Optional[str] = None,
        lora: Optional[str] = None,
        unet: Optional[str] = None,
        clip: Optional[str] = None,
        vae: Optional[str] = None,
    ) -> None:
        """Validate that the requested models are in the allowed whitelist.

        V1 constraint: models must be pre-approved. Non-whitelisted models
        are rejected immediately with model_not_allowed error.

        Args:
            checkpoint: Checkpoint filename (e.g., "sdxl.safetensors").
            lora: LoRA filename (e.g., "detail_enhancer.safetensors").

        Raises:
            ValueError: If any model is not in the whitelist, with
                "model_not_allowed" in the message.
        """
        whitelist = load_whitelist()
        allowed_checkpoints = whitelist["checkpoints"]
        allowed_loras = whitelist["loras"]
        allowed_unets = whitelist.get("unets", [])
        allowed_clip = whitelist.get("clip", [])
        allowed_vae = whitelist.get("vae", [])

        if checkpoint and checkpoint not in allowed_checkpoints:
            raise ModelNotAllowedError(checkpoint)

        if lora and lora not in allowed_loras:
            raise ModelNotAllowedError(lora)

        if unet and unet not in allowed_unets:
            raise ModelNotAllowedError(unet)

        if clip and clip not in allowed_clip:
            raise ModelNotAllowedError(clip)

        if vae and vae not in allowed_vae:
            raise ModelNotAllowedError(vae)

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

    def _build_error_event(self, job_id: str, code: str, detail: str) -> Dict[str, Any]:
        """Build a terminal error event compatible with JobEvent."""
        return {
            "event": "error",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": {"code": code, "detail": detail},
        }

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

    def _extract_workflow_models(self, engine: WorkflowEngine, graph: Dict[str, Any]) -> Dict[str, str]:
        """Collect checkpoint/lora filenames from a resolved workflow graph."""
        resolved_models: Dict[str, str] = {}
        prompt_nodes = graph.get("prompt", {})

        for semantic_name in ("checkpoint", "lora", "unet", "clip", "vae"):
            mapping = engine.manifest.inputs.get(semantic_name)
            if mapping is None:
                continue

            node = prompt_nodes.get(mapping.node_id, {})
            inputs = node.get("inputs", {})
            value = inputs.get(mapping.field)
            if isinstance(value, str) and value:
                resolved_models[semantic_name] = value

        return resolved_models

    def enqueue_modal_work(
        self,
        job_id: str,
        prompt: str,
        workflow_name: str = "txt2img",
        format: Optional[str] = None,
        checkpoint_url: Optional[str] = None,
        lora_url: Optional[str] = None,
        image_url: Optional[str] = None,
        control_image_url: Optional[str] = None,
        control_strength: Optional[float] = None,
        denoise: Optional[float] = None,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        ethnicity: Optional[str] = None,
        wardrobe: Optional[str] = None,
        expression: Optional[str] = None,
        background: Optional[str] = None,
        output_type: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality_mode: Optional[str] = None,
    ) -> None:
        """Enqueue Modal work for a job.

        V1 boundary: validates models against the whitelist before spawning,
        but does NOT perform runtime downloads. All models must already be
        pre-cached in the Modal Volume. Resolves the workflow with parameters
        and spawns the background generation task.

        Raises ValueError: If a model is not whitelisted (model_not_allowed) or
            a parameter is not declared by the workflow manifest.
        """
        workflow_name = workflow_name or "txt2img"
        is_product_workflow = workflow_name == "product_premium"
        is_persona_workflow = workflow_name == "realistic_persona"
        is_qwen_workflow = workflow_name == QWEN_WORKFLOW
        is_locked_model_workflow = workflow_name in LOCKED_MODEL_WORKFLOWS

        # Validate params against the manifest before resolving.
        src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        base_dir = os.path.join(src_root, "workflows", workflow_name)
        template_path = os.path.join(base_dir, "workflow.json")
        manifest_path = os.path.join(base_dir, "manifest.yaml")
        engine = WorkflowEngine(template_path, manifest_path)

        # Validate models before any spawning
        checkpoint_filename = (
            os.path.basename(checkpoint_url)
            if checkpoint_url and not is_locked_model_workflow
            else None
        )
        lora_filename = os.path.basename(lora_url) if lora_url and not is_locked_model_workflow else None
        self.validate_models(checkpoint=checkpoint_filename, lora=lora_filename)

        params = {"prompt": prompt}
        if checkpoint_url and not is_locked_model_workflow:
            params["checkpoint"] = os.path.basename(checkpoint_url)
        if lora_url and not is_locked_model_workflow:
            params["lora"] = os.path.basename(lora_url)
        if is_product_workflow:
            selected_format = format or "square"
            dimensions = engine.resolve_format_dimensions(selected_format)
            params["width"] = dimensions.width
            params["height"] = dimensions.height
        if is_qwen_workflow:
            params.update(resolve_qwen_quality_defaults(quality_mode or "high"))
            if width is not None:
                params["width"] = width
            if height is not None:
                params["height"] = height
        persona_values = (
            age,
            gender,
            ethnicity,
            wardrobe,
            expression,
            background,
            output_type,
        )
        params.update(
            {
                name: value
                for name, value in zip(PERSONA_PARAM_NAMES, persona_values)
                if value is not None
            }
        )
        if is_persona_workflow:
            params["image_url"] = image_url or ""
            params["faceid_strength"] = 0.75 if image_url else 0
        elif image_url:
            params["image_url"] = image_url
        if control_image_url:
            params["control_image_url"] = control_image_url
        if control_strength is not None:
            params["control_strength"] = control_strength
        if denoise is not None:
            params["denoise"] = denoise

        for key in params:
            if key not in engine.manifest.inputs:
                raise ValueError(
                    f"Parameter '{key}' is not supported by workflow '{workflow_name}'"
                )

        # V1 boundary: validate physical cache presence in the Modal Volume for
        # every model that is actually accepted by the workflow. Missing models
        # fail fast with error.code = "model_not_cached" before any Modal spawn.
        if checkpoint_filename is not None:
            resolve_cached_model(checkpoint_filename, "checkpoints")
        if lora_filename is not None:
            resolve_cached_model(lora_filename, "loras")

        resolved_graph = engine.execute(params)
        if is_qwen_workflow and (quality_mode or "high") == "fast":
            resolved_graph = inject_qwen_lightning_lora(resolved_graph)

        graph_models = self._extract_workflow_models(engine, resolved_graph)
        explicit_models = {
            "checkpoint": checkpoint_filename,
            "lora": lora_filename,
        }
        models_to_cache: Dict[str, str] = {}
        for semantic_name, filename in graph_models.items():
            if explicit_models.get(semantic_name) == filename:
                continue
            self.validate_models(**{semantic_name: filename})
            models_to_cache[semantic_name] = filename
        for semantic_name, filename in models_to_cache.items():
            resolve_cached_model(filename, MODEL_TYPE_BY_SEMANTIC_NAME[semantic_name])

        if is_qwen_workflow and (quality_mode or "high") == "fast":
            self.validate_models(lora=QWEN_LIGHTNING_LORA)
            resolve_cached_model(QWEN_LIGHTNING_LORA, "loras")

        from src.features.generation.modal_tasks import run_generation
        run_generation.spawn(job_id, resolved_graph)

    def _build_event(self, job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """Build a JobEvent-compatible dict from job state.

        Maps internal JobStore statuses to the public event enum. Legacy
        statuses such as ``pending`` and ``running`` are translated so the
        WebSocket contract always emits the granular V1 event names.
        """
        status = job["status"]

        # Map legacy/internal statuses to public event names.
        if status == "pending":
            event_type = "booting_server"
            progress = job.get("progress", 0)
            message = job.get("message", "Waiting to boot ComfyUI")
        elif status == "running":
            event_type = "generating"
            progress = job.get("progress", 50)
            message = job.get("message", "Processing")
        elif status in (
            "booting_server",
            "downloading_weights",
            "generating",
            "progress",
        ):
            event_type = status
            progress = job.get("progress", 0)
            message = job.get("message", "")
        else:
            event_type = status
            progress = None
            message = None

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
            if progress is not None:
                event["progress"] = progress
            if message is not None:
                event["message"] = message

        return event

    def get_job_events(self, job_id: str) -> Generator[Dict[str, Any], None, None]:
        """Yield lifecycle events for a job.

        Returns the current known state as a JobEvent-compatible dict.
        """
        job = self._store.get_job(job_id)
        if job is None:
            yield self._build_error_event(job_id, "job_not_found", "Job does not exist")
            return

        yield self._build_event(job_id, job)

    async def poll_job_events(self, job_id: str, interval: float = 0.5):
        """Async generator that polls job state and yields events until terminal.

        Yields a JobEvent-compatible dict each time the job state or progress
        changes. Stops when the job reaches a terminal state (completed or error).
        """
        import asyncio

        last_state = None
        while True:
            job = await self._store.aget_job(job_id)
            if job is None:
                yield self._build_error_event(
                    job_id, "job_not_found", "Job does not exist"
                )
                return

            event = self._build_event(job_id, job)
            # Compare state excluding the timestamp so we do not yield on every poll.
            comparable = {k: v for k, v in event.items() if k != "timestamp"}
            if comparable != last_state:
                yield event
                last_state = comparable

            if event["event"] in ["completed", "error"]:
                return

            await asyncio.sleep(interval)
