import os
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Any, Dict, Generator, Optional

from src.shared.errors import _sanitize_error_detail
from src.shared.flows.base import (
    BaseAtomicFlow,
    FlowOutput,
    GPUProfile,
    ImageArtifact,
    _validate_artifact_ownership as _base_validate_artifact_ownership,
)
from src.shared.job_store import JobStore
from src.shared.logging import get_logger
from src.shared.workflows.cache import load_whitelist, resolve_cached_model
from src.shared.workflows.engine import WorkflowEngine

_log = get_logger(__name__)


FLUX2_TXT2IMG_WORKFLOW = "flux2_txt2img"
FLUX2_EDITING_WORKFLOW = "flux2_editing"
EXTRACTION_FLOW = "extraction"
COMPOSITION_FLOW = "composition"
IDENTITY_FLOW = "identity"
SUPPORTED_WORKFLOWS = {
    FLUX2_TXT2IMG_WORKFLOW,
    FLUX2_EDITING_WORKFLOW,
    EXTRACTION_FLOW,
    COMPOSITION_FLOW,
    IDENTITY_FLOW,
}

MODEL_TYPE_BY_SEMANTIC_NAME = {
    "unet": "diffusion_models",
    "clip": "text_encoders",
    "lora": "loras",
    "vae": "vae",
    "checkpoint": "checkpoints",
    "pulid": "pulid",
    "face_detector": "face_detector",
    "control_net_name": "controlnets",
}


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
        session_id: str = "",
        resolve_asset_url: Callable[[str, str], str] | None = None,
    ) -> None:
        """Resolve and spawn a typed atomic flow.

        Loads the workflow engine for the flow's workflow_name, resolves
        parameters from the typed request, validates cached models, and
        spawns the correct Modal GPU function based on the flow's GPU profile.

        Args:
            job_id: Unique job identifier.
            flow_request: Typed flow request with ImageArtifact fields.
            session_id: Session UUID for input artifact ownership validation.
                Empty string (default) skips session matching for backward
                compatibility until SDD 3 upload migration.
            resolve_asset_url: Optional callable ``(asset_id, session_id) -> str``
                that resolves an ``asset_id`` to a fresh presigned GET URL.
                When provided and an ImageArtifact has ``asset_id`` set, the
                workflow graph is patched to use ``LoadImageFromUrl`` instead of
                ``LoadImage``, and the ``image_url`` input receives the resolved URL.
                Must raise ``ValueError`` with ``invalid_artifact`` for disallowed
                access.
        """
        engine = self._load_workflow_engine(flow_request.workflow_name)

        # Validate artifact ownership before processing
        self._validate_artifact_ownership(flow_request, session_id=session_id)

        # Build params from the typed request — only include fields
        # that the manifest declares as inputs.
        # Skip None values so manifest defaults (e.g. seed: -1) are used
        # rather than passing Python None to the engine.
        params: dict = {}
        # Track asset_id fields that need URL resolution
        asset_id_fields: dict[str, str] = {}
        for key in engine.manifest.inputs:
            if hasattr(flow_request, key):
                value = getattr(flow_request, key)
                if value is None:
                    continue
                if isinstance(value, ImageArtifact):
                    if value.asset_id and resolve_asset_url:
                        # Resolve asset_id -> presigned GET URL; the URL
                        # replaces the volume_path for LoadImageFromUrl
                        try:
                            presigned_url = resolve_asset_url(value.asset_id, session_id)
                        except ValueError as exc:
                            raise ValueError(str(exc))
                        params[key] = presigned_url
                        asset_id_fields[key] = value.asset_id
                    else:
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

        # Patch asset_id fields: replace their LoadImage nodes with
        # LoadImageFromUrl so the presigned URL is used instead of a volume path.
        if asset_id_fields:
            for field_name, asset_id in asset_id_fields.items():
                mapping = engine.manifest.inputs.get(field_name)
                if mapping is None:
                    continue
                node_id = mapping.node_id
                if node_id in resolved_graph.get("prompt", {}):
                    node = resolved_graph["prompt"][node_id]
                    original_class = node.get("class_type", "")
                    if original_class == "LoadImage":
                        # Replace LoadImage with LoadImageFromUrl
                        image_url = node["inputs"].get("image", "")
                        node["class_type"] = "LoadImageFromUrl"
                        node["inputs"]["image_url"] = image_url
                        del node["inputs"]["image"]

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
            run_generation_a100,
            run_generation_heavy,
        )

        gpu_task_map = {
            GPUProfile.T4: run_generation,
            GPUProfile.L4: run_generation_heavy,
            GPUProfile.A100: run_generation_a100,
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

    def _validate_artifact_ownership(
        self, flow_request: BaseAtomicFlow, session_id: str = ""
    ) -> None:
        """Validate that ImageArtifact fields reference valid sources.

        Each image artifact must either:
        - Reference a completed source_job_id (chained from another flow), or
        - Have a volume_path starting with ``input/`` (user-uploaded asset).

        When source_job_id is present and valid, the volume_path is
        overridden with the authoritative output from the source job to
        prevent arbitrary path injection via crafted artifacts.

        Additionally calls the base-level session ownership validation
        for each artifact. ``owner_session_id`` is NOT trusted — input/
        paths require a DB-verified ``asset_id`` when a session_id is
        provided (backward-compat: bare input/ is accepted when
        session_id is empty).
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
                # Security: reject cross-session artifact chaining — the source
                # job must be owned by the same session_id as the request.
                # An empty session_id does NOT bypass the check: if the source
                # job has a session, the request MUST provide a matching one.
                job_session = job.get("session_id", "")
                if job_session and session_id != job_session:
                    raise ValueError(
                        f"invalid_artifact: {field_name}.source_job_id "
                        f"'{art.source_job_id}' belongs to session "
                        f"'{job_session}' but request session is '{session_id}'"
                    )
                # Security: override volume_path with the authoritative output
                # from the completed job to prevent arbitrary path injection.
                # If the job has an R2 URL (presigned), use the local volume_path
                # for artifact chaining (the R2 URL is for display, not volume IO).
                image_path = job.get("image_path")
                r2_url = job.get("r2_url")
                if image_path and not r2_url:
                    art.volume_path = image_path
                elif not art.volume_path.startswith("input/"):
                    raise ValueError(
                        f"invalid_artifact: {field_name}.volume_path "
                        f"'{art.volume_path}' must start with 'input/' "
                        f"when source_job_id has no image_path"
                    )
            elif art.volume_path.startswith("input/"):
                # SDD 3 security: input/ paths MUST carry a DB-verifiable
                # asset_id. A client-provided owner_session_id is NOT accepted
                # as proof of ownership — it is spoofable and would let a
                # malicious client reference another session's uploaded file.
                # The asset_id is verified against the DB later via the
                # resolve_asset_url callback (AssetsService.get_active_asset).
                # When session_id is empty (backward-compat path with no
                # session enforcement), bare input/ is still accepted.
                if session_id and not art.asset_id:
                    raise ValueError(
                        f"invalid_artifact: {field_name}.volume_path "
                        f"'{art.volume_path}' requires a DB-verified "
                        f"asset_id for session-scoped access "
                        f"(owner_session_id is not trusted)"
                    )
            else:
                raise ValueError(
                    f"invalid_artifact: {field_name}.volume_path "
                    f"'{art.volume_path}' must start with 'input/' "
                    f"when no source_job_id is provided"
                )

            # Base-level session ownership validation
            _base_validate_artifact_ownership(art, session_id)

    def create_job(self, prompt: str, session_id: str = "") -> str:
        """Create a pending generation job for a non-empty prompt.

        Args:
            prompt: Generation prompt.
            session_id: Optional session UUID for ownership tracking.
        """
        if not prompt or len(prompt.strip()) == 0:
            raise ValueError("Prompt cannot be empty")
        return self._store.create_job(prompt, session_id=session_id)

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

        for key in params:
            if key not in engine.manifest.inputs:
                raise ValueError(
                    f"Parameter '{key}' is not supported by workflow '{workflow_name}'"
                )

        resolved_graph = engine.execute(params)
        self._validate_and_resolve_cached_models(engine, resolved_graph)

        from src.features.generation.modal_tasks import run_generation

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
            # Omit image_path from WS events — clients should use GET /images/{job_id}
            event["result"] = {}
        elif event_type == "error":
            _log.error(
                "job_error",
                job_id=job_id,
                error_code=job.get("error_code"),
                error_detail=_sanitize_error_detail(job.get("error_detail", "")),
            )
            event["error"] = {
                "code": job["error_code"],
                "detail": _sanitize_error_detail(job.get("error_detail", "")),
            }
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
