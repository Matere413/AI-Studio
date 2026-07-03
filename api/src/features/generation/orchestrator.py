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
from src.shared.storage import StorageError


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
        # Pre-planner: normalize selected assets (dedupe IDs, filter summaries).
        normalized = self._normalize_selected_assets(request)

        # Pre-planner: validate all selected assets are resolvable/ready.
        readiness_block = self._validate_selected_assets_readiness(
            normalized, session_id, resolve_asset_url
        )
        if readiness_block:
            return readiness_block

        try:
            decision = self._planner.plan(normalized)
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

        # Post-planner ambiguity guard: if the planner didn't ask for
        # clarification but multiple assets could fill the required roles,
        # ask before guessing.
        ambiguity = self._check_ambiguity(decision, normalized)
        if ambiguity:
            return ambiguity

        missing_roles = self._missing_roles(decision)
        if missing_roles:
            return self._missing_asset(missing_roles)

        unauthorized_roles = self._unauthorized_asset_roles(decision, normalized.selected_asset_ids)
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

    def _normalize_selected_assets(self, request: OrchestrateRequest) -> OrchestrateRequest:
        """Dedupe ``selected_asset_ids`` preserving first-seen order and filter
        ``selected_assets`` summaries to only include those whose IDs are in the
        deduped ID set.

        This ensures the planner receives a clean contract: no duplicate IDs
        and no summary orphans whose ID is not in the authoritative list.
        """
        seen: set[str] = set()
        deduped_ids: list[str] = []
        for asset_id in request.selected_asset_ids:
            if asset_id not in seen:
                seen.add(asset_id)
                deduped_ids.append(asset_id)

        id_set = set(deduped_ids)
        filtered_summaries = None
        if request.selected_assets is not None:
            filtered_summaries = [s for s in request.selected_assets if s.id in id_set]
            if not filtered_summaries:
                filtered_summaries = None

        # Preserve all other fields unchanged.
        return request.model_copy(update={
            "selected_asset_ids": deduped_ids,
            "selected_assets": filtered_summaries,
        })

    def _validate_selected_assets_readiness(
        self,
        request: OrchestrateRequest,
        session_id: str,
        resolve_asset_url: Callable[[str, str], str] | None,
    ) -> OrchestrateResponse | None:
        """Pre-planner validation: check every selected asset is resolvable.

        Uses the same ``resolve_asset_url`` callback as post-planner
        validation.  Any asset that raises ``ValueError`` (not found, not
        owned, not finalized) blocks the entire request before the planner
        runs, saving an LLM round-trip for invalid inputs.

        Returns ``None`` when all assets pass, or an ``OrchestrateResponse``
        with ``outcome="missing_asset"``.
        """
        if resolve_asset_url is None or not request.selected_asset_ids:
            return None

        blocked_roles: list[str] = []
        for asset_id in request.selected_asset_ids:
            try:
                resolve_asset_url(asset_id, session_id)
            except ValueError:
                blocked_roles.append(asset_id)
            except StorageError:
                return self._error(
                    "selected_asset_storage_unavailable",
                    "Selected asset storage is unavailable",
                    FailureContext(
                        planning_status="blocked",
                        validating_assets="blocked",
                        observe=True,
                        stage="validating_assets",
                    ),
                )
            except Exception:
                return self._error(
                    "selected_asset_storage_error",
                    "Selected asset storage validation failed",
                    FailureContext(
                        planning_status="blocked",
                        validating_assets="blocked",
                        observe=True,
                        stage="validating_assets",
                    ),
                )

        if not blocked_roles:
            return None

        # Pre-planner: we know which asset IDs failed but not which roles
        # they would fill — the planner hasn't run yet.  Return a
        # guidance-only response without populating missing_roles (which
        # is reserved for post-planner role-name values).
        return OrchestrateResponse(
            outcome="missing_asset",
            guidance=(
                f"Some selected assets are not ready: "
                f"{self._format_selected_asset_refs(request, blocked_roles)}. "
                "Please wait for uploads to complete, retry failed assets, "
                "or select different assets."
            ),
            stages=self._stages(planning="blocked", validating_assets="blocked"),
        )

    def _check_ambiguity(
        self,
        decision: PlannerDecision,
        request: OrchestrateRequest,
    ) -> OrchestrateResponse | None:
        """Post-planner ambiguity guard for compound-role or multi-candidate flows.

        When the planner produces a decision without clarification but the
        selected assets admit multiple valid role mappings, the orchestrator
        asks instead of letting the planner guess silently.

        Current rules:
        - **Composition**: if the number of selected assets exceeds the
          number of roles assigned AND no clarification was produced,
          ask which asset is background/foreground.
        - **Identity**: if multiple image-type selected assets exist and
          the planner assigned only one ``reference_face``, ask which face.
        - **Extraction**: same as identity for ``input_image``.
        """
        workflow = str(decision.workflow_name)
        if workflow not in ("extraction", "composition", "identity"):
            return None
        if decision.clarification:
            return None  # Planner already asked.

        image_candidate_ids = self._image_candidate_ids(request)
        num_selected = len(image_candidate_ids)
        required = REQUIRED_ROLES.get(workflow, [])
        num_assigned = sum(1 for r in required if r in decision.asset_roles)

        if workflow == "composition" and num_selected == num_assigned == 2:
            if not self._has_composition_role_evidence(request):
                return OrchestrateResponse(
                    outcome="clarification_required",
                    question="Which selected asset should be the background and which should be the foreground?",
                    stages=self._stages(planning="blocked"),
                )

        # Ambiguity threshold: more selected assets than required roles
        # assigned means the planner may have guessed which to use.
        if num_selected <= num_assigned:
            return None

        # Determine how many "optional" assets remain.
        assigned_ids = set(decision.asset_roles.values())
        unassigned = [aid for aid in image_candidate_ids if aid not in assigned_ids]

        if not unassigned:
            return None  # All assets were used.

        if workflow == "composition":
            return OrchestrateResponse(
                outcome="clarification_required",
                question=(
                    f"You have {len(unassigned)} extra selected asset(s). "
                    "Which asset should be the background and which the foreground?"
                ),
                stages=self._stages(planning="blocked"),
            )

        if workflow == "identity":
            return OrchestrateResponse(
                outcome="clarification_required",
                question=(
                    f"You selected {num_selected} assets. "
                    "Which one should I use as the identity reference face?"
                ),
                stages=self._stages(planning="blocked"),
            )

        # Extraction fallback
        return OrchestrateResponse(
            outcome="clarification_required",
            question=(
                f"You selected {num_selected} assets. "
                "Which one should I extract from?"
            ),
            stages=self._stages(planning="blocked"),
        )

    def _image_candidate_ids(self, request: OrchestrateRequest) -> list[str]:
        """Return selected IDs that can plausibly fill image workflow roles.

        ``selected_asset_ids`` remains canonical.  When client metadata is
        available, explicit ``media_type="file"`` summaries are excluded from
        image-role ambiguity checks; missing or unknown metadata remains a
        candidate so the guard fails closed.
        """
        if request.selected_assets is None:
            return request.selected_asset_ids

        summaries_by_id = {summary.id: summary for summary in request.selected_assets}
        candidates: list[str] = []
        for asset_id in request.selected_asset_ids:
            summary = summaries_by_id.get(asset_id)
            if summary is None or summary.media_type != "file":
                candidates.append(asset_id)
        return candidates

    def _has_composition_role_evidence(self, request: OrchestrateRequest) -> bool:
        text_parts = [request.prompt]
        if request.selected_assets:
            text_parts.extend(summary.name or "" for summary in request.selected_assets)
            text_parts.extend(summary.description or "" for summary in request.selected_assets)
            for summary in request.selected_assets:
                if summary.tags:
                    text_parts.extend(summary.tags)

        evidence = " ".join(text_parts).lower()
        return "background" in evidence and "foreground" in evidence

    def _format_selected_asset_refs(self, request: OrchestrateRequest, asset_ids: list[str]) -> str:
        summaries_by_id = {summary.id: summary for summary in request.selected_assets or []}
        refs: list[str] = []
        for asset_id in asset_ids:
            summary = summaries_by_id.get(asset_id)
            name = summary.name if summary else None
            refs.append(f"{name} ({asset_id})" if name else asset_id)
        return ", ".join(refs)

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
