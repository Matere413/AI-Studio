import base64
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

import httpx

from src.shared.flows.base import BaseAtomicFlow, FlowOutput, GPUProfile, ImageArtifact
from src.shared.job_store import JobStore
from src.shared.workflows.cache import load_whitelist, resolve_cached_model
from src.shared.workflows.engine import WorkflowEngine


FLUX2_TXT2IMG_WORKFLOW = "flux2_txt2img"
FLUX2_EDITING_WORKFLOW = "flux2_editing"
IDENTIDAD_GGUF_WORKFLOW = "identidad_gguf"
EXTRACTION_FLOW = "extraction"
COMPOSITION_FLOW = "composition"
SUPPORTED_WORKFLOWS = {
    FLUX2_TXT2IMG_WORKFLOW,
    FLUX2_EDITING_WORKFLOW,
    IDENTIDAD_GGUF_WORKFLOW,
    EXTRACTION_FLOW,
    COMPOSITION_FLOW,
}

MODEL_TYPE_BY_SEMANTIC_NAME = {
    "unet": "diffusion_models",
    "clip": "text_encoders",
    "lora": "loras",
    "vae": "vae",
    "checkpoint": "checkpoints",
    "gguf": "gguf",
    "pulid": "pulid",
    "face_detector": "face_detector",
    "control_net_name": "controlnets",
}


def resolve_identity_seed(seed: Optional[int]) -> int:
    """Resolve identidad_gguf seed, replacing -1/None with a runtime seed."""
    if seed is None or seed == -1:
        return secrets.randbelow(2**63)
    return seed


def download_image_to_base64(image_url: str) -> str:
    """Download an HTTP reference image and encode it for LoadImageFromBase64."""
    if image_url.startswith("data:image/"):
        return image_url
    if not image_url.startswith(("http://", "https://")):
        raise ValueError("image_url must be an http(s) URL or data URI")

    response = httpx.get(image_url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "image/png").split(";", 1)[0]
    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


class ModelNotAllowedError(ValueError):
    """Raised when a requested model is not in the allowed whitelist."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        super().__init__(
            f"model_not_allowed: Model '{model_id}' is not in the allowed whitelist."
        )


class GenerationService:
    """Business logic for generation job lifecycle management."""

    def __init__(self, job_store: JobStore):
        self._store = job_store

    def validate_models(
        self,
        checkpoint: Optional[str] = None,
        lora: Optional[str] = None,
        unet: Optional[str] = None,
        clip: Optional[str] = None,
        vae: Optional[str] = None,
        gguf: Optional[str] = None,
        pulid: Optional[str] = None,
        face_detector: Optional[str] = None,
        control_net_name: Optional[str] = None,
    ) -> None:
        """Validate that requested/default workflow models are whitelisted."""
        whitelist = load_whitelist()
        allowed_by_name = {
            "checkpoint": whitelist.get("checkpoints", []),
            "lora": whitelist.get("loras", []),
            "unet": whitelist.get("unets", []),
            "clip": whitelist.get("clip", []),
            "vae": whitelist.get("vae", []),
            "gguf": whitelist.get("gguf", []),
            "pulid": whitelist.get("pulid", []),
            "face_detector": whitelist.get("face_detector", []),
            "control_net_name": whitelist.get("controlnets", []),
        }
        requested = {
            "checkpoint": checkpoint,
            "lora": lora,
            "unet": unet,
            "clip": clip,
            "vae": vae,
            "gguf": gguf,
            "pulid": pulid,
            "face_detector": face_detector,
            "control_net_name": control_net_name,
        }

        for semantic_name, filename in requested.items():
            if not filename:
                continue
            allowed_name = os.path.basename(filename) if semantic_name == "face_detector" else filename
            if allowed_name not in allowed_by_name[semantic_name]:
                raise ModelNotAllowedError(filename)

    def dispatch_flow(
        self,
        job_id: str,
        flow_request: BaseAtomicFlow,
    ) -> None:
        """Resolve and spawn a typed atomic flow.

        Loads the workflow engine for the flow's workflow_name, resolves
        parameters from the typed request, validates cached models, and
        spawns the correct Modal GPU function based on the flow's GPU profile.
        """
        engine = self._load_workflow_engine(flow_request.workflow_name)

        # Validate artifact ownership before processing
        self._validate_artifact_ownership(flow_request)

        # Build params from the typed request — only include fields
        # that the manifest declares as inputs
        params: dict = {}
        for key in engine.manifest.inputs:
            if hasattr(flow_request, key):
                value = getattr(flow_request, key)
                if isinstance(value, ImageArtifact):
                    params[key] = value.volume_path
                else:
                    params[key] = value

        # Resolve control_mode → control_net_name for the composition flow
        if flow_request.workflow_name == "composition":
            from src.shared.flows.composition import CompositionRequest, CompositionFlow
            if isinstance(flow_request, (CompositionRequest, CompositionFlow)):
                control_net_map = {
                    "depth": "flux-controlnet-depth-v1.safetensors",
                    "canny": "flux-controlnet-canny-v1.safetensors",
                }
                params["control_net_name"] = control_net_map[flow_request.control_mode]

        resolved_graph = engine.execute(params)
        self._validate_and_resolve_cached_models(engine, resolved_graph)

        # For composition flow, select preprocessor based on control_mode
        if flow_request.workflow_name == "composition":
            from src.shared.flows.composition import CompositionRequest, CompositionFlow
            if isinstance(flow_request, (CompositionRequest, CompositionFlow)):
                if flow_request.control_mode == "canny":
                    resolved_graph["prompt"]["15"]["inputs"]["image"] = ["19", 0]

        # Select the correct Modal task based on GPU profile
        from src.features.generation.modal_tasks import (
            run_generation,
            run_generation_heavy,
        )

        gpu_task_map = {
            GPUProfile.T4: run_generation,
            GPUProfile.L4: run_generation_heavy,
            GPUProfile.A100: run_generation_heavy,
        }
        task_fn = gpu_task_map.get(flow_request.gpu_profile, run_generation_heavy)

        # Pass output artifacts config from the manifest for persistence
        output_artifacts = engine.manifest.outputs.get("artifacts", [])

        # Pass the flow's timeout_s as pipeline_timeout_s so the ComfyUI
        # execution respects the flow's SLO instead of the hardcoded default
        task_fn.spawn(
            job_id,
            resolved_graph,
            output_artifacts,
            pipeline_timeout_s=flow_request.timeout_s,
        )

    def _validate_artifact_ownership(self, flow_request: BaseAtomicFlow) -> None:
        """Validate that ImageArtifact fields reference valid sources.

        Each image artifact must either:
        - Reference a completed source_job_id (chained from another flow), or
        - Have a volume_path starting with ``input/`` (user-uploaded asset).

        This prevents arbitrary path injection via crafted artifacts.
        """
        for field_name in type(flow_request).model_fields:
            field_value = getattr(flow_request, field_name)
            if not isinstance(field_value, ImageArtifact):
                continue
            art = field_value
            if art.source_job_id:
                job = self._store.get_job(art.source_job_id)
                if job is None or job.get("status") != "completed":
                    raise ValueError(
                        f"invalid_artifact: {field_name}.source_job_id "
                        f"'{art.source_job_id}' does not reference a completed job"
                    )
            elif not art.volume_path.startswith("input/"):
                raise ValueError(
                    f"invalid_artifact: {field_name}.volume_path "
                    f"'{art.volume_path}' must start with 'input/' "
                    f"when no source_job_id is provided"
                )

    def create_job(self, prompt: str) -> str:
        """Create a pending generation job for a non-empty prompt."""
        if not prompt or len(prompt.strip()) == 0:
            raise ValueError("Prompt cannot be empty")
        return self._store.create_job(prompt)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by job_id."""
        return self._store.get_job(job_id)

    def map_failure_to_error(self, code: str, detail: str) -> Dict[str, str]:
        """Map a failure to a terminal error structure."""
        return {"code": code, "detail": detail}

    def _build_error_event(self, job_id: str, code: str, detail: str) -> Dict[str, Any]:
        return {
            "event": "error",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": {"code": code, "detail": detail},
        }

    def resolve_workflow(self, workflow_name: str = FLUX2_TXT2IMG_WORKFLOW, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolve a workflow template with runtime parameters."""
        engine = self._load_workflow_engine(workflow_name)
        return engine.execute(params or {})

    def _load_workflow_engine(self, workflow_name: str) -> WorkflowEngine:
        if workflow_name not in SUPPORTED_WORKFLOWS:
            raise ValueError(f"unsupported_workflow: Workflow '{workflow_name}' is not supported")

        src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        base_dir = os.path.join(src_root, "workflows", workflow_name)
        return WorkflowEngine(
            os.path.join(base_dir, "workflow.json"),
            os.path.join(base_dir, "manifest.yaml"),
        )

    def _extract_workflow_models(self, engine: WorkflowEngine, graph: Dict[str, Any]) -> Dict[str, str]:
        """Collect model filenames from a resolved workflow graph."""
        resolved_models: Dict[str, str] = {}
        prompt_nodes = graph.get("prompt", {})

        for semantic_name in MODEL_TYPE_BY_SEMANTIC_NAME:
            mapping = engine.manifest.inputs.get(semantic_name)
            if mapping is None:
                continue

            node = prompt_nodes.get(mapping.node_id, {})
            value = node.get("inputs", {}).get(mapping.field)
            if isinstance(value, str) and value:
                resolved_models[semantic_name] = value

        return resolved_models

    def _validate_and_resolve_cached_models(
        self,
        engine: WorkflowEngine,
        resolved_graph: Dict[str, Any],
    ) -> None:
        for semantic_name, filename in self._extract_workflow_models(engine, resolved_graph).items():
            self.validate_models(**{semantic_name: filename})
            resolve_cached_model(filename, MODEL_TYPE_BY_SEMANTIC_NAME[semantic_name])

    def enqueue_modal_work(
        self,
        job_id: str,
        prompt: str,
        workflow_name: str = FLUX2_TXT2IMG_WORKFLOW,
        use_turbo: bool = True,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> None:
        """Resolve a supported workflow and spawn the appropriate Modal task."""
        workflow_name = workflow_name or FLUX2_TXT2IMG_WORKFLOW
        engine = self._load_workflow_engine(workflow_name)

        params: Dict[str, Any] = {"prompt": prompt}
        if workflow_name in {FLUX2_TXT2IMG_WORKFLOW, FLUX2_EDITING_WORKFLOW}:
            params["use_turbo"] = use_turbo
        if workflow_name == FLUX2_EDITING_WORKFLOW:
            if not image_base64:
                raise ValueError("missing_image_base64: image_base64 is required for flux2_editing")
            params["image_base64"] = image_base64
        if workflow_name == IDENTIDAD_GGUF_WORKFLOW:
            if not image_url:
                raise ValueError("image_url is required for workflow 'identidad_gguf'")
            params["image_url"] = ""
            params["seed"] = resolve_identity_seed(seed)
            if width is not None:
                params["width"] = width
            if height is not None:
                params["height"] = height

        for key in params:
            if key not in engine.manifest.inputs:
                raise ValueError(
                    f"Parameter '{key}' is not supported by workflow '{workflow_name}'"
                )

        resolved_graph = engine.execute(params)
        self._validate_and_resolve_cached_models(engine, resolved_graph)

        from src.features.generation.modal_tasks import run_generation, run_generation_heavy

        if workflow_name == IDENTIDAD_GGUF_WORKFLOW:
            image_mapping = engine.manifest.inputs["image_url"]
            resolved_graph["prompt"][image_mapping.node_id]["inputs"][image_mapping.field] = download_image_to_base64(image_url)
            run_generation_heavy.spawn(job_id, resolved_graph)
            return

        run_generation.spawn(job_id, resolved_graph)

    def _build_event(self, job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """Build a JobEvent-compatible dict from job state."""
        status = job["status"]
        if status == "pending":
            event_type = "booting_server"
            progress = job.get("progress", 0)
            message = job.get("message", "Waiting to boot ComfyUI")
        elif status == "running":
            event_type = "generating"
            progress = job.get("progress", 50)
            message = job.get("message", "Processing")
        elif status in ("booting_server", "downloading_weights", "generating", "progress"):
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
        job = self._store.get_job(job_id)
        if job is None:
            yield self._build_error_event(job_id, "job_not_found", "Job does not exist")
            return
        yield self._build_event(job_id, job)

    async def poll_job_events(self, job_id: str, interval: float = 0.5):
        import asyncio

        last_state = None
        while True:
            job = await self._store.aget_job(job_id)
            if job is None:
                yield self._build_error_event(job_id, "job_not_found", "Job does not exist")
                return

            event = self._build_event(job_id, job)
            comparable = {k: v for k, v in event.items() if k != "timestamp"}
            if comparable != last_state:
                yield event
                last_state = comparable

            if event["event"] in ["completed", "error"]:
                return

            await asyncio.sleep(interval)
