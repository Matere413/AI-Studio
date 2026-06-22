import pytest
from pydantic import ValidationError
from src.features.generation.models import (
    GenerateRequest,
    GenerateResponse,
    JobEvent,
    JobEventError,
    JobEventResult,
)


class TestGenerateRequest:
    """Unit tests for GenerateRequest Pydantic model."""

    def test_valid_request(self):
        """GIVEN a valid non-empty prompt
        WHEN creating a GenerateRequest
        THEN the model validates successfully.
        """
        request = GenerateRequest(prompt="a cyberpunk cat reading a book")
        assert request.prompt == "a cyberpunk cat reading a book"

    def test_empty_prompt_rejected(self):
        """GIVEN an empty prompt
        WHEN creating a GenerateRequest
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateRequest(prompt="")

    def test_prompt_too_long_rejected(self):
        """GIVEN a prompt exceeding 4000 characters
        WHEN creating a GenerateRequest
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateRequest(prompt="x" * 4001)

    def test_prompt_at_max_length_accepted(self):
        """GIVEN a prompt exactly at 4000 characters
        WHEN creating a GenerateRequest
        THEN the model validates successfully.
        """
        request = GenerateRequest(prompt="x" * 4000)
        assert request.prompt == "x" * 4000

    def test_missing_prompt_rejected(self):
        """GIVEN no prompt is provided
        WHEN creating a GenerateRequest
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateRequest()

    def test_no_extra_fields_allowed(self):
        """GIVEN extra fields are provided
        WHEN creating a GenerateRequest
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateRequest(prompt="valid prompt", extra="field")


class TestFlux2GenerateRequest:
    """Unit tests for the Flux 2 generation request contract."""

    def test_defaults_to_flux2_txt2img_with_turbo_enabled(self):
        """GIVEN a prompt-only request
        WHEN creating a GenerateRequest
        THEN Flux 2 text-to-image is selected with turbo enabled by default.
        """
        request = GenerateRequest(prompt="a cinematic white orchid")

        assert request.workflow_name == "flux2_txt2img"
        assert request.use_turbo is True
        assert request.image_base64 is None

    @pytest.mark.parametrize("use_turbo", [True, False])
    def test_flux2_txt2img_accepts_turbo_toggle(self, use_turbo):
        """GIVEN a Flux 2 text-to-image request
        WHEN use_turbo is provided
        THEN the model preserves the explicit toggle value.
        """
        request = GenerateRequest(
            prompt="premium product photo on marble",
            workflow="flux2_txt2img",
            use_turbo=use_turbo,
        )

        assert request.workflow == "flux2_txt2img"
        assert request.use_turbo is use_turbo

    def test_flux2_editing_requires_and_preserves_base64_image(self):
        """GIVEN a Flux 2 editing request with base64 image input
        WHEN creating a GenerateRequest
        THEN the edit image and turbo toggle validate successfully.
        """
        request = GenerateRequest(
            prompt="replace the background with warm studio light",
            workflow_name="flux2_editing",
            image_base64="data:image/png;base64,aGVsbG8=",
            use_turbo=False,
        )

        assert request.workflow_name == "flux2_editing"
        assert request.image_base64 == "data:image/png;base64,aGVsbG8="
        assert request.use_turbo is False

    @pytest.mark.parametrize("workflow_name", ["qwen_txt2img", "realistic_persona", "product_premium", "txt2img", "identidad_gguf"])
    def test_rejects_legacy_workflow_values(self, workflow_name):
        """GIVEN a retired workflow value (including identidad_gguf)
        WHEN creating a GenerateRequest
        THEN Pydantic rejects it before service dispatch.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(prompt="legacy prompt", workflow_name=workflow_name)

        assert workflow_name in str(exc_info.value)

    @pytest.mark.parametrize(
        ("legacy_field", "legacy_value"),
        [
            ("checkpoint_url", "https://example.com/model.safetensors"),
            ("lora_url", "https://example.com/lora.safetensors"),
            ("quality_mode", "fast"),
            ("format", "vertical"),
            ("age", 42),
        ],
    )
    def test_rejects_retired_legacy_fields(self, legacy_field, legacy_value):
        """GIVEN fields owned by retired workflows
        WHEN creating a GenerateRequest
        THEN extra-field validation rejects the payload.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(prompt="legacy controls", **{legacy_field: legacy_value})

        assert legacy_field in str(exc_info.value)

    def test_flux2_txt2img_rejects_image_base64(self):
        """GIVEN an image_base64 value on a text-to-image request
        WHEN creating a GenerateRequest
        THEN validation rejects the editing-only image input.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="a prompt",
                workflow_name="flux2_txt2img",
                image_base64="data:image/png;base64,aGVsbG8=",
            )

        assert "image_base64" in str(exc_info.value)
        assert "flux2_editing" in str(exc_info.value)

    def test_flux2_editing_rejects_missing_image_base64(self):
        """GIVEN a Flux 2 editing request without image_base64
        WHEN creating a GenerateRequest
        THEN validation rejects the incomplete edit payload.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(prompt="edit prompt", workflow="flux2_editing")

        assert "image_base64" in str(exc_info.value)

    def test_identidad_gguf_workflow_is_rejected(self):
        """GIVEN a request for the retired identidad_gguf workflow
        WHEN creating a GenerateRequest
        THEN validation rejects the deprecated workflow name.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="legacy prompt",
                workflow_name="identidad_gguf",
                image_url="https://example.com/reference-face.png",
            )

        assert "identidad_gguf" in str(exc_info.value)
        assert "not supported" in str(exc_info.value)

    def test_identidad_gguf_fields_are_rejected(self):
        """GIVEN a request with legacy identidad_gguf fields (image_url, width, height, seed)
        WHEN creating a GenerateRequest
        THEN validation rejects the deprecated fields.
        """
        with pytest.raises(ValidationError):
            GenerateRequest(
                prompt="legacy identity",
                workflow_name="flux2_txt2img",
                image_url="https://example.com/face.png",
            )


class TestGenerateResponse:
    """Unit tests for GenerateResponse Pydantic model."""

    def test_valid_response(self):
        """GIVEN a valid job_id
        WHEN creating a GenerateResponse
        THEN the model validates with status='pending'.
        """
        response = GenerateResponse(job_id="job-123")
        assert response.job_id == "job-123"
        assert response.status == "pending"

    def test_missing_job_id_rejected(self):
        """GIVEN no job_id is provided
        WHEN creating a GenerateResponse
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateResponse()

    def test_empty_job_id_rejected(self):
        """GIVEN an empty job_id
        WHEN creating a GenerateResponse
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateResponse(job_id="")

    def test_no_extra_fields_allowed(self):
        """GIVEN extra fields are provided
        WHEN creating a GenerateResponse
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            GenerateResponse(job_id="job-123", extra="field")


class TestJobEvent:
    """Unit tests for JobEvent Pydantic model."""

    def test_booting_server_event(self):
        """GIVEN a booting_server event
        WHEN creating a JobEvent
        THEN the model validates with required fields.
        """
        event = JobEvent(
            event="booting_server",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            progress=0,
            message="Booting ComfyUI server",
        )
        assert event.event == "booting_server"
        assert event.job_id == "job-123"
        assert event.progress == 0
        assert event.message == "Booting ComfyUI server"

    def test_generating_event(self):
        """GIVEN a generating event
        WHEN creating a JobEvent
        THEN the model validates with progress and message.
        """
        event = JobEvent(
            event="generating",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            progress=50,
            message="Generating image",
        )
        assert event.progress == 50
        assert event.message == "Generating image"

    def test_progress_event(self):
        """GIVEN a progress event
        WHEN creating a JobEvent
        THEN the model validates with numeric progress.
        """
        event = JobEvent(
            event="progress",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            progress=75,
            message="Step 15/20",
        )
        assert event.progress == 75
        assert event.message == "Step 15/20"

    def test_downloading_weights_event(self):
        """GIVEN a downloading_weights event
        WHEN creating a JobEvent
        THEN the model validates with progress and message.
        """
        event = JobEvent(
            event="downloading_weights",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            progress=10,
            message="Cache validation",
        )
        assert event.event == "downloading_weights"

    def test_completed_event(self):
        """GIVEN a completed event
        WHEN creating a JobEvent
        THEN the model validates without requiring result.
        """
        event = JobEvent(
            event="completed",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
        )
        assert event.event == "completed"
        assert event.result is None

    def test_error_event(self):
        """GIVEN an error event
        WHEN creating a JobEvent
        THEN the model validates with error.code and error.detail.
        """
        event = JobEvent(
            event="error",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            error=JobEventError(code="job_not_found", detail="Job does not exist"),
        )
        assert event.error.code == "job_not_found"
        assert event.error.detail == "Job does not exist"

    def test_error_event_model_not_allowed(self):
        """GIVEN an error event with model_not_allowed code
        WHEN creating a JobEvent
        THEN the model validates with the new error code.
        """
        event = JobEvent(
            event="error",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            error=JobEventError(code="model_not_allowed", detail="Model not in whitelist"),
        )
        assert event.error.code == "model_not_allowed"

    def test_error_event_timeout(self):
        """GIVEN an error event with timeout code
        WHEN creating a JobEvent
        THEN the model validates with the timeout error code.
        """
        event = JobEvent(
            event="error",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            error=JobEventError(code="timeout", detail="Generation exceeded 300s deadline"),
        )
        assert event.error.code == "timeout"

    def test_invalid_event_type_rejected(self):
        """GIVEN an invalid event type
        WHEN creating a JobEvent
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            JobEvent(
                event="invalid",
                job_id="job-123",
                timestamp="2026-06-11T12:00:00Z",
            )

    def test_progress_out_of_range_rejected(self):
        """GIVEN a progress value outside 0-100
        WHEN creating a JobEvent
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            JobEvent(
                event="running",
                job_id="job-123",
                timestamp="2026-06-11T12:00:00Z",
                progress=101,
            )

    def test_no_extra_fields_allowed(self):
        """GIVEN extra fields are provided
        WHEN creating a JobEvent
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            JobEvent(
                event="pending",
                job_id="job-123",
                timestamp="2026-06-11T12:00:00Z",
                extra="field",
            )

    def test_completed_without_result_allowed(self):
        """GIVEN a completed event without result
        WHEN creating a JobEvent
        THEN the model validates (result is optional; client uses GET /images/{job_id}).
        """
        event = JobEvent(
            event="completed",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
        )
        assert event.event == "completed"
        assert event.result is None

    def test_error_without_error_details_rejected(self):
        """GIVEN an error event without error details
        WHEN creating a JobEvent
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            JobEvent(
                event="error",
                job_id="job-123",
                timestamp="2026-06-11T12:00:00Z",
            )
