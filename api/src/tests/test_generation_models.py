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


class TestProductPremiumGenerateRequest:
    """Unit tests for product premium request validation."""

    def test_product_workflow_accepts_vertical_format(self):
        """GIVEN a product premium workflow request
        WHEN workflow and format are provided
        THEN the request validates successfully.
        """
        request = GenerateRequest(
            prompt="premium studio product photo",
            workflow="product_premium",
            format="vertical",
        )

        assert request.workflow == "product_premium"
        assert request.format == "vertical"

    def test_legacy_workflow_name_accepts_square_format(self):
        """GIVEN a legacy workflow_name request
        WHEN product premium format is square
        THEN the request validates successfully.
        """
        request = GenerateRequest(
            prompt="premium studio product photo",
            workflow_name="product_premium",
            format="square",
        )

        assert request.workflow_name == "product_premium"
        assert request.format == "square"

    def test_non_product_workflow_rejects_vertical_format(self):
        """GIVEN a non-product workflow
        WHEN a vertical format is requested
        THEN validation fails.
        """
        with pytest.raises(ValidationError):
            GenerateRequest(
                prompt="legacy product photo",
                workflow_name="txt2img",
                format="vertical",
            )

    def test_conflicting_workflow_aliases_rejected(self):
        """GIVEN both workflow fields are supplied with conflicting values
        WHEN creating a GenerateRequest
        THEN validation fails with a clear error.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="premium studio product photo",
                workflow="product_premium",
                workflow_name="txt2img",
                format="square",
            )

        assert "workflow" in str(exc_info.value)
        assert "workflow_name" in str(exc_info.value)

    def test_matching_workflow_aliases_are_accepted(self):
        """GIVEN both workflow fields are supplied with the same value
        WHEN creating a GenerateRequest
        THEN validation succeeds.
        """
        request = GenerateRequest(
            prompt="premium studio product photo",
            workflow="product_premium",
            workflow_name="product_premium",
            format="square",
        )

        assert request.workflow == "product_premium"
        assert request.workflow_name == "product_premium"


class TestRealisticPersonaGenerateRequest:
    """Unit tests for realistic persona request validation."""

    @pytest.mark.parametrize(
        ("image_url", "expected_image_url"),
        [
            ("https://example.com/reference-face.png", "https://example.com/reference-face.png"),
            ("http://example.com/reference-face.jpg", "http://example.com/reference-face.jpg"),
            ("data:image/png;base64,iVBORw0KGgo=", "data:image/png;base64,iVBORw0KGgo="),
            (None, None),
        ],
    )
    def test_realistic_persona_validates_reference_image_url_formats(self, image_url, expected_image_url):
        """GIVEN a realistic persona request with an optional reference image
        WHEN creating a GenerateRequest
        THEN http(s) URLs, data URIs, and None validate successfully.
        """
        request = GenerateRequest(
            prompt="cinematic realistic portrait",
            workflow="realistic_persona",
            image_url=image_url,
        )

        assert request.image_url == expected_image_url

    @pytest.mark.parametrize(
        "image_url",
        [
            "ftp://example.com/reference-face.png",
            "example.com/reference-face.png",
            "not-a-reference-image",
        ],
    )
    def test_realistic_persona_rejects_invalid_reference_image_url_formats(self, image_url):
        """GIVEN a realistic persona request with an invalid reference image URL
        WHEN creating a GenerateRequest
        THEN validation fails before dispatch.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="cinematic realistic portrait",
                workflow="realistic_persona",
                image_url=image_url,
            )

        assert "image_url" in str(exc_info.value)

    def test_non_persona_workflow_rejects_reference_image_url(self):
        """GIVEN a non-persona workflow request with a reference image
        WHEN creating a GenerateRequest
        THEN validation fails because image_url is persona-scoped.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="legacy prompt",
                workflow_name="txt2img",
                image_url="https://example.com/reference-face.png",
            )

        assert "image_url" in str(exc_info.value)
        assert "realistic_persona" in str(exc_info.value)

    def test_realistic_persona_accepts_declared_controls(self):
        """GIVEN a realistic persona request with all declared controls
        WHEN creating a GenerateRequest
        THEN the model validates the typed persona contract.
        """
        request = GenerateRequest(
            prompt="cinematic realistic portrait",
            workflow="realistic_persona",
            age=42,
            gender="woman",
            ethnicity="Latina",
            wardrobe="linen blazer",
            expression="warm confident smile",
            background="window-lit studio",
            output_type="portrait",
        )

        assert request.workflow == "realistic_persona"
        assert request.age == 42
        assert request.gender == "woman"
        assert request.ethnicity == "Latina"
        assert request.wardrobe == "linen blazer"
        assert request.expression == "warm confident smile"
        assert request.background == "window-lit studio"
        assert request.output_type == "portrait"

    def test_realistic_persona_rejects_age_below_range(self):
        """GIVEN a realistic persona request with age below 18
        WHEN creating a GenerateRequest
        THEN validation fails for the age range.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="cinematic realistic portrait",
                workflow_name="realistic_persona",
                age=5,
            )

        assert "age" in str(exc_info.value)

    def test_realistic_persona_rejects_unknown_output_type(self):
        """GIVEN a realistic persona request with an undeclared output type
        WHEN creating a GenerateRequest
        THEN validation fails against declared persona output types.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="cinematic realistic portrait",
                workflow="realistic_persona",
                output_type="panoramic",
            )

        assert "output_type" in str(exc_info.value)
        assert "portrait" in str(exc_info.value)
        assert "full-body" in str(exc_info.value)

    def test_non_persona_workflow_rejects_persona_controls(self):
        """GIVEN a non-persona workflow request with persona-only controls
        WHEN creating a GenerateRequest
        THEN validation fails because those controls are workflow-scoped.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="legacy product photo",
                workflow_name="txt2img",
                age=42,
            )

        assert "age" in str(exc_info.value)
        assert "realistic_persona" in str(exc_info.value)


class TestQwenTxt2ImgGenerateRequest:
    """Unit tests for the qwen_txt2img request contract."""

    def test_qwen_workflow_accepts_dynamic_dimensions_and_fast_quality(self):
        """GIVEN a qwen_txt2img request with dynamic dimensions and fast mode
        WHEN creating a GenerateRequest
        THEN the typed request preserves all Qwen-specific controls.
        """
        request = GenerateRequest(
            prompt="high fidelity product image",
            workflow="qwen_txt2img",
            width=1280,
            height=768,
            quality_mode="fast",
        )

        assert request.workflow == "qwen_txt2img"
        assert request.width == 1280
        assert request.height == 768
        assert request.quality_mode == "fast"

    def test_qwen_workflow_defaults_quality_mode_to_high(self):
        """GIVEN a qwen_txt2img request without quality_mode
        WHEN creating a GenerateRequest
        THEN quality_mode defaults to high quality.
        """
        request = GenerateRequest(
            prompt="high fidelity product image",
            workflow_name="qwen_txt2img",
            width=1024,
            height=1024,
        )

        assert request.quality_mode == "high"

    @pytest.mark.parametrize(
        ("width", "height"),
        [
            (300, 1024),
            (1024, 300),
            (192, 1024),
            (1024, 2112),
        ],
    )
    def test_qwen_workflow_rejects_invalid_dimensions(self, width, height):
        """GIVEN invalid Qwen dimensions
        WHEN creating a GenerateRequest
        THEN validation fails before service dispatch.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="high fidelity product image",
                workflow="qwen_txt2img",
                width=width,
                height=height,
            )

        assert "invalid_dimensions" in str(exc_info.value)

    def test_non_qwen_workflow_rejects_explicit_qwen_dimensions(self):
        """GIVEN a legacy workflow request with Qwen-only dimensions
        WHEN creating a GenerateRequest
        THEN validation fails because dimensions are scoped to qwen_txt2img.
        """
        with pytest.raises(ValidationError) as exc_info:
            GenerateRequest(
                prompt="legacy product photo",
                workflow_name="txt2img",
                width=1024,
                height=1024,
            )

        assert "width" in str(exc_info.value)
        assert "qwen_txt2img" in str(exc_info.value)


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
        THEN the model validates with result.image_path.
        """
        event = JobEvent(
            event="completed",
            job_id="job-123",
            timestamp="2026-06-11T12:00:00Z",
            result=JobEventResult(image_path="/path/to/image.png"),
        )
        assert event.result.image_path == "/path/to/image.png"

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

    def test_completed_without_result_rejected(self):
        """GIVEN a completed event without result
        WHEN creating a JobEvent
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            JobEvent(
                event="completed",
                job_id="job-123",
                timestamp="2026-06-11T12:00:00Z",
            )

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
