from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.features.generation.models import (
    OrchestrateRequest,
    OrchestrateResponse,
    OrchestrateStage,
    PlannerDecision,
)
from src.features.generation.planner import EnvPlannerClient, PlannerClient
from src.features.generation.service import GenerationService
from src.shared.flows.base import ImageArtifact
from src.shared.flows.composition import CompositionFlow
from src.shared.flows.extraction import ExtractionFlow
from src.shared.flows.identity import IdentityFlow
from src.shared.logging import get_logger


_log = get_logger(__name__)

# PlannerDecision knows every workflow the product may support, including legacy
# Flux 2 editing. This PR 1 orchestrator allowlist is intentionally narrower:
# asset-backed flux2_editing dispatch needs a separate resolver-to-base64 bridge.
CONFIDENCE_THRESHOLD = 0.70
ALLOWED_WORKFLOWS = {"extraction", "composition", "identity", "flux2_txt2img"}
REQUIRED_ROLES = {
    "extraction": ["input_image"],
    "composition": ["background_image", "foreground_image"],
    "identity": ["reference_face"],
    "flux2_txt2img": [],
}
PARAM_ALLOWLIST = {
    "extraction": {"mask_margin", "prompt"},
    "composition": {"control_mode", "control_strength", "seed", "prompt"},
    "identity": {"width", "height", "seed", "prompt"},
    "flux2_txt2img": {"use_turbo", "prompt"},
}
RAW_GRAPH_KEYS = {"nodes", "graph", "workflow_json"}


@dataclass(frozen=True)
class FailureContext:
    planning_status: str = "blocked"
    validating_assets: str = "pending"
    job_id: str | None = None
    observe: bool = False
    stage: str = "planning"
    workflow: str | None = None
    terminal_state_recovery_failed: bool = False


class Orchestrator:
    def __init__(
        self,
        planner: PlannerClient | None = None,
        dispatch_job: Callable[..., None] | None = None,
    ):
        self._planner = planner or EnvPlannerClient()
        self._dispatch_job = dispatch_job

    def orchestrate(
        self,
        request: OrchestrateRequest,
        service: GenerationService,
        session_id: str,
        resolve_asset_url: Callable[[str, str], str] | None = None,
    ) -> OrchestrateResponse:
        try:
            decision = self._planner.plan(request)
        except ValueError as exc:
            return self._planner_error(exc)
        except Exception as exc:
            return self._error(
                "planner_provider_unavailable",
                "Planner provider is unavailable",
                FailureContext(planning_status="blocked", observe=True, stage="planning"),
            )

        if decision.confidence < CONFIDENCE_THRESHOLD or decision.clarification:
            return OrchestrateResponse(
                outcome="clarification_required",
                question=decision.clarification or "Could you clarify what you want to create or edit?",
                stages=self._stages(planning="blocked"),
            )

        validation_error = self._validate_decision(decision)
        if validation_error:
            return validation_error

        missing_roles = self._missing_roles(decision)
        if missing_roles:
            return self._missing_asset(missing_roles)

        unauthorized_roles = self._unauthorized_asset_roles(decision, request.selected_asset_ids)
        if unauthorized_roles:
            return OrchestrateResponse(
                outcome="missing_asset",
                missing_roles=unauthorized_roles,
                guidance="Please select the required asset again before generating.",
                stages=self._stages(planning="completed", validating_assets="blocked"),
            )

        resolver_rejected_roles = self._resolver_rejected_asset_roles(decision, session_id, resolve_asset_url)
        if resolver_rejected_roles:
            return OrchestrateResponse(
                outcome="missing_asset",
                missing_roles=resolver_rejected_roles,
                guidance="Please select the required asset again before generating.",
                stages=self._stages(planning="completed", validating_assets="blocked"),
            )

        job_id = None
        try:
            job_id = service.create_job(request.prompt, session_id=session_id)
            self._dispatch(decision, request, service, job_id, session_id, resolve_asset_url)
        except ValueError as exc:
            if job_id:
                return self._dispatch_failure_response(service, job_id, decision)
            return self._error(
                "validation_error",
                str(exc),
                FailureContext(
                    planning_status="completed",
                    validating_assets="blocked",
                    observe=True,
                    stage="validation",
                    workflow=str(decision.workflow_name),
                ),
            )
        except Exception as exc:
            if job_id:
                return self._dispatch_failure_response(service, job_id, decision)
            return self._error(
                "dispatch_failed",
                "Dispatch failed",
                FailureContext(
                    planning_status="completed",
                    observe=True,
                    stage="dispatching",
                    workflow=str(decision.workflow_name),
                ),
            )

        return OrchestrateResponse(
            outcome="job_started",
            job_id=job_id,
            status="pending",
            stages=self._stages(
                planning="completed",
                validating_assets="completed",
                dispatching="completed",
                generating="pending",
            ),
        )

    def _validate_decision(self, decision: PlannerDecision) -> OrchestrateResponse | None:
        workflow = str(decision.workflow_name)
        if workflow not in ALLOWED_WORKFLOWS:
            return self._error(
                "unsupported_workflow",
                f"Workflow '{workflow}' is not supported",
                FailureContext(observe=True, stage="validation", workflow=workflow),
            )
        if RAW_GRAPH_KEYS.intersection(decision.params):
            return self._error(
                "raw_graph_payload",
                "Planner output must not include ComfyUI graph payloads",
                FailureContext(observe=True, stage="validation", workflow=workflow),
            )
        unsupported_params = set(decision.params) - PARAM_ALLOWLIST[workflow]
        if unsupported_params:
            _log.warning("unsupported_params_ignored", workflow=workflow, params=list(unsupported_params))
            for p in unsupported_params:
                decision.params.pop(p, None)
        return None

    def _missing_roles(self, decision: PlannerDecision) -> list[str]:
        workflow = str(decision.workflow_name)
        declared_missing = list(decision.missing_assets)
        required_missing = [role for role in REQUIRED_ROLES[workflow] if role not in decision.asset_roles]
        return list(dict.fromkeys(declared_missing + required_missing))

    def _unauthorized_asset_roles(self, decision: PlannerDecision, selected_asset_ids: list[str]) -> list[str]:
        selected = set(selected_asset_ids)
        return [role for role, asset_id in decision.asset_roles.items() if asset_id not in selected]

    def _resolver_rejected_asset_roles(
        self,
        decision: PlannerDecision,
        session_id: str,
        resolve_asset_url: Callable[[str, str], str] | None,
    ) -> list[str]:
        if resolve_asset_url is None:
            return []
        rejected_roles: list[str] = []
        for role, asset_id in decision.asset_roles.items():
            try:
                resolve_asset_url(asset_id, session_id)
            except ValueError:
                rejected_roles.append(role)
        return rejected_roles

    def _mark_job_failed(self, service: GenerationService, job_id: str, code: str, detail: str) -> bool:
        try:
            service._store.update_job(job_id, "error", error_code=code, error_detail=detail)
            return True
        except Exception:
            _log.error(
                "terminal_state_recovery_failed",
                job_id=job_id,
                error_code=code,
            )
            return False

    def _dispatch_failure_response(
        self,
        service: GenerationService,
        job_id: str,
        decision: PlannerDecision,
    ) -> OrchestrateResponse:
        terminal_update_failed = not self._mark_job_failed(service, job_id, "dispatch_failed", "Dispatch failed")
        return self._error(
            "dispatch_failed",
            "Dispatch failed",
            FailureContext(
                planning_status="completed",
                validating_assets="completed",
                job_id=job_id,
                observe=True,
                stage="dispatching",
                workflow=str(decision.workflow_name),
                terminal_state_recovery_failed=terminal_update_failed,
            ),
        )

    def _dispatch(
        self,
        decision: PlannerDecision,
        request: OrchestrateRequest,
        service: GenerationService,
        job_id: str,
        session_id: str,
        resolve_asset_url: Callable[[str, str], str] | None,
    ) -> None:
        workflow = str(decision.workflow_name)
        params = decision.params
        dispatcher = self._dispatch_job or service.dispatch_flow
        if workflow == "flux2_txt2img":
            service.enqueue_modal_work(
                job_id=job_id,
                prompt=request.prompt,
                workflow_name="flux2_txt2img",
                use_turbo=bool(params.get("use_turbo", True)),
            )
            return
        flow_request = self._build_flow_request(workflow, request.prompt, decision)
        dispatcher(
            job_id=job_id,
            flow_request=flow_request,
            session_id=session_id,
            resolve_asset_url=resolve_asset_url,
        )

    def _build_flow_request(self, workflow: str, prompt: str, decision: PlannerDecision):
        if workflow == "extraction":
            return ExtractionFlow(
                prompt=prompt,
                input_image=self._artifact(decision.asset_roles["input_image"]),
                **self._filtered_params(decision, "extraction"),
            )
        if workflow == "composition":
            return CompositionFlow(
                prompt=prompt,
                background_image=self._artifact(decision.asset_roles["background_image"]),
                foreground_image=self._artifact(decision.asset_roles["foreground_image"]),
                control_mode=decision.params.get("control_mode", "depth"),
                **{k: v for k, v in self._filtered_params(decision, "composition").items() if k != "control_mode"},
            )
        if workflow == "identity":
            return IdentityFlow(
                prompt=prompt,
                reference_face=self._artifact(decision.asset_roles["reference_face"]),
                **self._filtered_params(decision, "identity"),
            )
        raise ValueError(f"unsupported_workflow: Workflow '{workflow}' is not supported")

    def _filtered_params(self, decision: PlannerDecision, workflow: str) -> dict[str, Any]:
        return {k: v for k, v in decision.params.items() if k in PARAM_ALLOWLIST[workflow]}

    def _artifact(self, asset_id: str) -> ImageArtifact:
        return ImageArtifact(volume_path=f"input/{asset_id}", asset_id=asset_id)

    def _missing_asset(self, missing_roles: list[str]) -> OrchestrateResponse:
        return OrchestrateResponse(
            outcome="missing_asset",
            missing_roles=missing_roles,
            guidance=f"Please upload or select: {', '.join(missing_roles)}.",
            stages=self._stages(planning="completed", validating_assets="blocked"),
        )

    def _error(
        self,
        error_code: str,
        detail: str,
        context: FailureContext | None = None,
    ) -> OrchestrateResponse:
        context = context or FailureContext()
        if context.observe:
            self._observe_failure(
                error_code=error_code,
                stage=context.stage,
                workflow=context.workflow,
                job_id=context.job_id,
                terminal_state_recovery_failed=context.terminal_state_recovery_failed,
            )
        return OrchestrateResponse(
            outcome="error",
            job_id=context.job_id,
            error_code=error_code,
            error_detail=detail,
            stages=self._stages(planning=context.planning_status, validating_assets=context.validating_assets),
        )

    def _planner_error(self, exc: ValueError) -> OrchestrateResponse:
        message = str(exc)
        if message.startswith("planner_provider_unavailable"):
            return self._error(
                "planner_provider_unavailable",
                "Planner provider is unavailable",
                FailureContext(planning_status="blocked", observe=True, stage="planning"),
            )
        if message.startswith("planner_provider_invalid_response"):
            return self._error(
                "planner_provider_invalid_response",
                "Planner provider response is invalid",
                FailureContext(planning_status="blocked", observe=True, stage="planning"),
            )
        if message.startswith("planner_unconfigured"):
            return self._error(
                "planner_unconfigured",
                "Planner provider is not configured",
                FailureContext(planning_status="blocked", observe=True, stage="planning"),
            )
        return self._error(
            "planner_schema_invalid",
            "Planner response does not match the required schema",
            FailureContext(planning_status="blocked", observe=True, stage="planning"),
        )

    def _observe_failure(
        self,
        error_code: str,
        stage: str,
        workflow: str | None = None,
        job_id: str | None = None,
        terminal_state_recovery_failed: bool = False,
    ) -> None:
        metadata: dict[str, Any] = {
            "error_code": error_code,
            "stage": stage,
        }
        if workflow:
            metadata["workflow"] = workflow
        if job_id:
            metadata["job_id"] = job_id
        if terminal_state_recovery_failed:
            metadata["terminal_state_recovery_failed"] = True
        _log.error("orchestration_failure", **metadata)

    def _stages(
        self,
        planning: str = "pending",
        validating_assets: str = "pending",
        dispatching: str = "pending",
        generating: str = "pending",
    ) -> list[OrchestrateStage]:
        return [
            OrchestrateStage(name="planning", status=planning),
            OrchestrateStage(name="validating_assets", status=validating_assets),
            OrchestrateStage(name="dispatching", status=dispatching),
            OrchestrateStage(name="generating", status=generating),
        ]
