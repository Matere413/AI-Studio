import json
from unittest.mock import Mock, patch
from types import SimpleNamespace
import urllib.error

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from src.features.generation.models import OrchestrateRequest, PlannerDecision
from src.features.generation.orchestrator import Orchestrator
from src.features.generation.planner import EnvPlannerClient, parse_planner_decision
from src.features.generation.router import router as generation_router, set_planner_client, set_resolve_asset_url
from src.features.generation.service import GenerationService
from src.shared.job_store import JobStore
from src.tests.client_helpers import LazyTestClient


def _decision(**overrides):
    data = {
        "workflow_name": "extraction",
        "asset_roles": {"input_image": "asset-product"},
        "params": {},
        "confidence": 0.92,
    }
    data.update(overrides)
    return PlannerDecision(**data)


class TestOrchestrationModels:
    def test_orchestrate_request_accepts_prompt_assets_and_context(self):
        request = OrchestrateRequest(
            prompt="Extract this product",
            selected_asset_ids=["asset-product"],
            workspace_context={"brand": "Blanca"},
        )

        assert request.prompt == "Extract this product"
        assert request.selected_asset_ids == ["asset-product"]
        assert request.workspace_context == {"brand": "Blanca"}

    def test_planner_decision_rejects_raw_graph_payloads(self):
        with pytest.raises(ValidationError) as exc_info:
            PlannerDecision(
                workflow_name="extraction",
                asset_roles={"input_image": "asset-product"},
                params={"nodes": {"1": {"class_type": "KSampler"}}},
                confidence=0.95,
            )

        assert "raw_graph_payload" in str(exc_info.value)


class TestEnvPlannerSelectedAssets:
    """``EnvPlannerClient.plan()`` MUST pass ``selected_assets`` metadata to
    the planner context when provided, and omit it when not provided."""

    def test_plan_includes_selected_assets_when_provided(self, monkeypatch):
        """GIVEN an OrchestrateRequest WITH selected_assets
        WHEN EnvPlannerClient.plan() builds the planner payload
        THEN the payload includes selected_assets metadata.
        """
        captured = {}

        def capture_urlopen(*args, **kwargs):
            import json
            body = json.loads(args[0].data)
            captured["payload"] = body
            # Return a valid OpenAI-compatible planner response so plan()
            # doesn't fail on the response shape.
            decision = (
                '{"workflow_name":"extraction","asset_roles":'
                '{"input_image":"asset-1"},"params":{},"confidence":0.92}'
            )
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): return None
                def read(self): return json.dumps({
                    "choices": [{"message": {"content": decision}}]
                }).encode("utf-8")
            return FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
        client = EnvPlannerClient(api_url="https://planner.example.test", model="planner-model")

        client.plan(OrchestrateRequest(
            prompt="Extract this product",
            selected_asset_ids=["asset-1", "asset-2"],
            selected_assets=[
                {"id": "asset-1", "name": "Product Photo", "media_type": "image"},
                {"id": "asset-2", "name": "Background", "media_type": "image"},
            ],
        ))

        ctx = json.loads(captured["payload"]["messages"][1]["content"])
        assert "selected_assets" in ctx, (
            "selected_assets must be included in planner context when provided"
        )
        assert len(ctx["selected_assets"]) == 2
        assert ctx["selected_assets"][0]["id"] == "asset-1"
        assert ctx["selected_assets"][0]["name"] == "Product Photo"

    def test_plan_omits_selected_assets_when_none(self, monkeypatch):
        """GIVEN an OrchestrateRequest WITHOUT selected_assets
        WHEN EnvPlannerClient.plan() builds the planner payload
        THEN selected_assets is NOT included in the planner context.
        """
        captured = {}

        def capture_urlopen(*args, **kwargs):
            import json
            body = json.loads(args[0].data)
            captured["payload"] = body
            decision = (
                '{"workflow_name":"extraction","asset_roles":'
                '{"input_image":"asset-1"},"params":{},"confidence":0.92}'
            )
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): return None
                def read(self): return json.dumps({
                    "choices": [{"message": {"content": decision}}]
                }).encode("utf-8")
            return FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
        client = EnvPlannerClient(api_url="https://planner.example.test", model="planner-model")

        client.plan(OrchestrateRequest(
            prompt="Extract this product",
            selected_asset_ids=["asset-1"],
        ))

        ctx = json.loads(captured["payload"]["messages"][1]["content"])
        assert "selected_assets" not in ctx, (
            "selected_assets must NOT be present in planner context when not provided"
        )

    def test_plan_normalizes_selected_assets_as_list_of_dicts(self, monkeypatch):
        """GIVEN selected_assets as SelectedAssetSummary Pydantic models
        WHEN EnvPlannerClient.plan() builds the payload
        THEN selected_assets is serialized as a list of dicts in the context.
        """
        captured = {}

        def capture_urlopen(*args, **kwargs):
            import json
            body = json.loads(args[0].data)
            captured["payload"] = body
            decision = (
                '{"workflow_name":"extraction","asset_roles":'
                '{"input_image":"asset-1"},"params":{},"confidence":0.92}'
            )
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): return None
                def read(self): return json.dumps({
                    "choices": [{"message": {"content": decision}}]
                }).encode("utf-8")
            return FakeResponse()

        monkeypatch.setattr("urllib.request.urlopen", capture_urlopen)
        client = EnvPlannerClient(api_url="https://planner.example.test", model="planner-model")

        client.plan(OrchestrateRequest(
            prompt="Extract this product",
            selected_asset_ids=["asset-1"],
            selected_assets=[
                {"id": "asset-1", "name": "Product", "tags": ["hero", "new"]},
            ],
        ))

        ctx = json.loads(captured["payload"]["messages"][1]["content"])
        assert ctx["selected_assets"] == [
            {"id": "asset-1", "name": "Product", "tags": ["hero", "new"]},
        ], "selected_assets must contain full serialized summaries"


class TestPlannerParsing:
    def test_parse_planner_decision_validates_json_schema(self):
        decision = parse_planner_decision(
            '{"workflow_name":"identity","asset_roles":{"reference_face":"asset-face"},"params":{"seed":42},"confidence":0.91}'
        )

        assert decision.workflow_name == "identity"
        assert decision.asset_roles == {"reference_face": "asset-face"}
        assert decision.params == {"seed": 42}
        assert decision.confidence == 0.91

    def test_parse_planner_decision_rejects_malformed_output(self):
        with pytest.raises(ValueError, match="planner_schema_invalid"):
            parse_planner_decision("not-json")

    def test_env_planner_normalizes_network_failures(self, monkeypatch):
        def fail_urlopen(*args, **kwargs):
            raise urllib.error.URLError("provider hostname leaked")

        monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
        client = EnvPlannerClient(api_url="https://planner.example.test", model="planner-model")

        with pytest.raises(ValueError, match="planner_provider_unavailable") as exc_info:
            client.plan(OrchestrateRequest(prompt="Extract this product"))

        assert "provider hostname leaked" not in str(exc_info.value)

    def test_env_planner_rejects_invalid_provider_response_shape(self, monkeypatch):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self):
                return b'{"unexpected":"shape"}'

        monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())
        client = EnvPlannerClient(api_url="https://planner.example.test", model="planner-model")

        with pytest.raises(ValueError, match="planner_provider_invalid_response") as exc_info:
            client.plan(OrchestrateRequest(prompt="Extract this product"))

        assert "unexpected" not in str(exc_info.value)


class TestOrchestrator:
    def test_low_confidence_returns_clarification_without_dispatch(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision(confidence=0.41, clarification="What should be improved?")
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="make it better"),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "clarification_required"
        assert response.question == "What should be improved?"
        assert response.stages[0].status == "blocked"
        dispatch.assert_not_called()

    def test_missing_required_asset_returns_guidance_without_dispatch(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision(
            workflow_name="identity",
            asset_roles={},
            missing_assets=["reference_face"],
            confidence=0.93,
        )
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Preserve this person's identity"),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "missing_asset"
        assert response.missing_roles == ["reference_face"]
        assert "upload or select" in response.guidance
        assert response.stages[1].status == "blocked"
        dispatch.assert_not_called()

    def test_valid_extraction_plan_dispatches_typed_flow(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision()
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
            resolve_asset_url=lambda asset_id, session_id: f"https://r2.example.com/{asset_id}",
        )

        assert response.outcome == "job_started"
        assert response.status == "pending"
        assert response.job_id
        flow_request = dispatch.call_args.kwargs["flow_request"]
        assert flow_request.workflow_name == "extraction"
        assert flow_request.input_image.asset_id == "asset-product"
        assert flow_request.input_image.volume_path == "input/asset-product"

    def test_unauthorized_asset_id_returns_missing_asset_guidance(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision(asset_roles={"input_image": "asset-owned-by-someone-else"})
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "missing_asset"
        assert response.missing_roles == ["input_image"]
        assert "select the required asset again" in response.guidance
        dispatch.assert_not_called()

    def test_valid_flux2_txt2img_plan_uses_existing_modal_enqueue(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision(
            workflow_name="flux2_txt2img",
            asset_roles={},
            params={"use_turbo": False},
        )
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        with pytest.MonkeyPatch.context() as monkeypatch:
            enqueue = Mock()
            monkeypatch.setattr(service, "enqueue_modal_work", enqueue)
            response = orchestrator.orchestrate(
                request=OrchestrateRequest(prompt="Create a studio product image"),
                service=service,
                session_id="session-1",
            )

        assert response.outcome == "job_started"
        assert enqueue.call_args.kwargs["workflow_name"] == "flux2_txt2img"
        assert enqueue.call_args.kwargs["use_turbo"] is False
        dispatch.assert_not_called()

    def test_unsafe_workflow_is_rejected_before_dispatch(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = SimpleNamespace(
            workflow_name="raw_graph",
            asset_roles={},
            params={},
            confidence=0.92,
            clarification=None,
            missing_assets=[],
        )
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Run this custom graph", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "error"
        assert response.error_code == "unsupported_workflow"
        dispatch.assert_not_called()

    def test_unsupported_workflow_is_observed_with_safe_metadata(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = SimpleNamespace(
            workflow_name="raw_graph",
            asset_roles={},
            params={},
            confidence=0.92,
            clarification=None,
            missing_assets=[],
        )
        orchestrator = Orchestrator(planner=planner, dispatch_job=Mock())

        with patch("src.features.generation.orchestrator._log") as log:
            response = orchestrator.orchestrate(
                request=OrchestrateRequest(prompt="Run this custom graph", selected_asset_ids=["asset-product"]),
                service=service,
                session_id="session-1",
            )

        assert response.outcome == "error"
        assert response.error_code == "unsupported_workflow"
        log.error.assert_called_once()
        assert log.error.call_args.args == ("orchestration_failure",)
        assert log.error.call_args.kwargs["error_code"] == "unsupported_workflow"
        assert log.error.call_args.kwargs["workflow"] == "raw_graph"
        assert log.error.call_args.kwargs["stage"] == "validation"

    def test_planner_provider_failure_returns_safe_error_without_dispatch(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.side_effect = TimeoutError("secret provider timeout detail")
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "error"
        assert response.error_code == "planner_provider_unavailable"
        assert "secret provider timeout detail" not in response.error_detail
        dispatch.assert_not_called()

    def test_planner_invalid_response_is_observed_with_safe_metadata(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.side_effect = ValueError("planner_provider_invalid_response: secret raw payload")
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        with patch("src.features.generation.orchestrator._log") as log:
            response = orchestrator.orchestrate(
                request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
                service=service,
                session_id="session-1",
            )

        assert response.outcome == "error"
        assert response.error_code == "planner_provider_invalid_response"
        assert "secret raw payload" not in response.error_detail
        log.error.assert_called_once()
        assert log.error.call_args.args == ("orchestration_failure",)
        assert log.error.call_args.kwargs["error_code"] == "planner_provider_invalid_response"
        assert log.error.call_args.kwargs["stage"] == "planning"
        assert "secret raw payload" not in str(log.error.call_args.kwargs)
        dispatch.assert_not_called()

    def test_planner_schema_invalid_returns_safe_error_without_raw_content(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.side_effect = ValueError(
            "planner_schema_invalid: secret raw provider payload with invalid_field"
        )
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        with patch("src.features.generation.orchestrator._log") as log:
            response = orchestrator.orchestrate(
                request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
                service=service,
                session_id="session-1",
            )

        assert response.outcome == "error"
        assert response.error_code == "planner_schema_invalid"
        assert response.error_detail == "Planner response does not match the required schema"
        assert "secret raw provider payload" not in response.error_detail
        assert "invalid_field" not in response.error_detail
        log.error.assert_called_once()
        assert log.error.call_args.kwargs["error_code"] == "planner_schema_invalid"
        assert "secret raw provider payload" not in str(log.error.call_args.kwargs)
        dispatch.assert_not_called()

    def test_flux2_editing_plan_is_deferred_safely_for_backend_pr1(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision(
            workflow_name="flux2_editing",
            asset_roles={"image_asset_id": "asset-product"},
            params={},
        )
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Edit this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
        )

        assert response.outcome == "error"
        assert response.error_code == "unsupported_workflow"
        dispatch.assert_not_called()

    def test_resolver_rejected_asset_returns_missing_asset_without_dispatch(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision()
        dispatch = Mock()
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
            resolve_asset_url=lambda asset_id, session_id: (_ for _ in ()).throw(ValueError("invalid_artifact: not owned")),
        )

        assert response.outcome == "missing_asset"
        assert response.missing_roles == ["input_image"]
        assert "select the required asset again" in response.guidance
        dispatch.assert_not_called()

    def test_dispatch_failure_marks_created_job_failed(self):
        store = JobStore()
        service = GenerationService(store)
        planner = Mock()
        planner.plan.return_value = _decision()
        dispatch = Mock(side_effect=ValueError("dispatch exploded"))
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        response = orchestrator.orchestrate(
            request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
            service=service,
            session_id="session-1",
            resolve_asset_url=lambda asset_id, session_id: f"https://r2.example.com/{asset_id}",
        )

        assert response.outcome == "error"
        assert response.job_id
        job = service.get_job(response.job_id)
        assert job["status"] == "error"
        assert job["error_code"] == "dispatch_failed"

    def test_dispatch_failure_is_observed_when_terminal_state_update_fails(self):
        class FailingUpdateStore(JobStore):
            def update_job(self, *args, **kwargs):
                raise RuntimeError("database secret detail")

        service = GenerationService(FailingUpdateStore())
        planner = Mock()
        planner.plan.return_value = _decision()
        dispatch = Mock(side_effect=ValueError("dispatch secret detail"))
        orchestrator = Orchestrator(planner=planner, dispatch_job=dispatch)

        with patch("src.features.generation.orchestrator._log") as log:
            response = orchestrator.orchestrate(
                request=OrchestrateRequest(prompt="Extract this product", selected_asset_ids=["asset-product"]),
                service=service,
                session_id="session-1",
                resolve_asset_url=lambda asset_id, session_id: f"https://r2.example.com/{asset_id}",
            )

        assert response.outcome == "error"
        assert response.error_code == "dispatch_failed"
        assert response.job_id
        assert "secret" not in response.error_detail
        events = [call.args[0] for call in log.error.call_args_list]
        assert events == ["terminal_state_recovery_failed", "orchestration_failure"]
        recovery_kwargs = log.error.call_args_list[0].kwargs
        assert recovery_kwargs["job_id"] == response.job_id
        assert recovery_kwargs["error_code"] == "dispatch_failed"
        assert "database secret detail" not in str(recovery_kwargs)
        failure_kwargs = log.error.call_args_list[1].kwargs
        assert failure_kwargs["terminal_state_recovery_failed"] is True
        assert "dispatch secret detail" not in str(failure_kwargs)


class TestOrchestrateEndpoint:
    @pytest.fixture(autouse=True)
    def _planner_and_resolver(self):
        planner = Mock()
        planner.plan.return_value = _decision()
        set_planner_client(planner)
        set_resolve_asset_url(lambda asset_id, session_id: f"https://r2.example.com/{asset_id}")
        yield planner
        set_planner_client(None)
        set_resolve_asset_url(None)

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(generation_router)
        return LazyTestClient(app)

    def test_generate_orchestrate_returns_202_for_started_job(self, client):
        with MockDispatchFlow():
            response = client.post(
                "/generate/orchestrate",
                json={"prompt": "Extract this product", "selected_asset_ids": ["asset-product"]},
                headers={"X-Session-ID": "session-1"},
            )

        assert response.status_code == 202
        assert response.json()["outcome"] == "job_started"
        assert response.json()["status"] == "pending"

    def test_generate_orchestrate_returns_200_for_clarification(self, client, _planner_and_resolver):
        _planner_and_resolver.plan.return_value = _decision(
            confidence=0.2,
            clarification="What should be improved?",
        )

        response = client.post(
            "/generate/orchestrate",
            json={"prompt": "make it better"},
            headers={"X-Session-ID": "session-1"},
        )

        assert response.status_code == 200
        assert response.json()["outcome"] == "clarification_required"
        assert response.json()["question"] == "What should be improved?"

    def test_generate_orchestrate_returns_non_2xx_for_error_outcome(self, client, _planner_and_resolver):
        _planner_and_resolver.plan.return_value = SimpleNamespace(
            workflow_name="raw_graph",
            asset_roles={},
            params={},
            confidence=0.92,
            clarification=None,
            missing_assets=[],
        )

        response = client.post(
            "/generate/orchestrate",
            json={"prompt": "Run this custom graph", "selected_asset_ids": ["asset-product"]},
            headers={"X-Session-ID": "session-1"},
        )

        assert response.status_code == 422
        assert response.json()["outcome"] == "error"
        assert response.json()["error_code"] == "unsupported_workflow"

    def test_generate_orchestrate_schema_invalid_error_does_not_leak_raw_planner_content(
        self, client, _planner_and_resolver
    ):
        _planner_and_resolver.plan.side_effect = ValueError(
            "planner_schema_invalid: secret raw provider payload with invalid_field"
        )

        response = client.post(
            "/generate/orchestrate",
            json={"prompt": "Extract this product", "selected_asset_ids": ["asset-product"]},
            headers={"X-Session-ID": "session-1"},
        )

        assert response.status_code == 422
        assert response.json()["outcome"] == "error"
        assert response.json()["error_code"] == "planner_schema_invalid"
        assert response.json()["error_detail"] == "Planner response does not match the required schema"
        assert "secret raw provider payload" not in response.text
        assert "invalid_field" not in response.text


class MockDispatchFlow:
    def __enter__(self):
        self._patch = pytest.MonkeyPatch()
        self._patch.setattr("src.features.generation.service.GenerationService.dispatch_flow", Mock())
        return self

    def __exit__(self, exc_type, exc, tb):
        self._patch.undo()
