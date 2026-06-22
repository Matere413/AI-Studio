"""Unit tests for BaseAtomicFlow, ImageArtifact, FlowOutput, GPUProfile,
and artifact ownership validation."""

import pytest
from pydantic import ValidationError

from src.shared.flows.base import (
    BaseAtomicFlow,
    FlowOutput,
    GPUProfile,
    ImageArtifact,
    _validate_artifact_ownership,
)


class TestGPUProfile:
    """Unit tests for GPUProfile enum."""

    def test_has_l4_member(self):
        assert GPUProfile.L4.value == "L4"

    def test_has_a100_member(self):
        assert GPUProfile.A100.value == "A100"


class TestImageArtifact:
    """Unit tests for ImageArtifact validation."""

    def test_valid_png_artifact(self):
        """GIVEN a valid PNG artifact with volume_path
        WHEN creating an ImageArtifact
        THEN the model validates successfully.
        """
        artifact = ImageArtifact(
            volume_path="output/job-123/output.png",
            media_type="image/png",
            source_job_id="job-123",
            width=1024,
            height=1024,
        )
        assert artifact.volume_path == "output/job-123/output.png"
        assert artifact.media_type == "image/png"
        assert artifact.source_job_id == "job-123"

    def test_valid_jpeg_artifact(self):
        """GIVEN a valid JPEG artifact
        WHEN creating an ImageArtifact
        THEN the model validates with image/jpeg.
        """
        artifact = ImageArtifact(
            volume_path="output/job-456/result.jpeg",
            media_type="image/jpeg",
        )
        assert artifact.media_type == "image/jpeg"

    def test_default_media_type_is_png(self):
        """GIVEN an ImageArtifact without explicit media_type
        WHEN created
        THEN the default is image/png.
        """
        artifact = ImageArtifact(volume_path="output/job-1/file.png")
        assert artifact.media_type == "image/png"

    @pytest.mark.parametrize(
        "invalid_media_type",
        [
            "image/webp",
            "image/gif",
            "image/svg+xml",
            "application/pdf",
            "text/plain",
        ],
    )
    def test_invalid_media_type_rejected(self, invalid_media_type):
        """GIVEN an unsupported media_type
        WHEN creating an ImageArtifact
        THEN validation rejects with error.code = "invalid_media_type".
        """
        with pytest.raises(ValidationError) as exc_info:
            ImageArtifact(
                volume_path="output/job-1/file.png",
                media_type=invalid_media_type,
            )
        error_msg = str(exc_info.value)
        assert "invalid_media_type" in error_msg or "media_type" in error_msg

    @pytest.mark.parametrize(
        "malicious_path",
        [
            "../../../etc/passwd",
            "../other/volume/escaped.png",
            "attack/../../malicious",
            "output/../etc/passwd",
        ],
    )
    def test_path_traversal_rejected(self, malicious_path):
        """GIVEN a volume_path that attempts path traversal
        WHEN creating an ImageArtifact
        THEN validation rejects with error.code = "invalid_artifact".
        """
        with pytest.raises(ValidationError) as exc_info:
            ImageArtifact(
                volume_path=malicious_path,
                media_type="image/png",
            )
        error_msg = str(exc_info.value)
        assert "invalid_artifact" in error_msg or "volume_path" in error_msg or "traversal" in error_msg

    def test_safe_nested_path_accepted(self):
        """GIVEN a volume_path within the job volume root
        WHEN creating an ImageArtifact
        THEN validation succeeds.
        """
        artifact = ImageArtifact(
            volume_path="output/job-789/nested/deep/file.png",
            media_type="image/png",
        )
        assert artifact.volume_path == "output/job-789/nested/deep/file.png"

    def test_empty_volume_path_rejected(self):
        """GIVEN an empty volume_path
        WHEN creating an ImageArtifact
        THEN validation fails.
        """
        with pytest.raises(ValidationError):
            ImageArtifact(
                volume_path="",
                media_type="image/png",
            )

    @pytest.mark.parametrize(
        "abs_path",
        [
            "/etc/passwd",
            "/root/ComfyUI/output/evil.png",
            "/var/log/system.log",
            "/tmp/escape.png",
        ],
    )
    def test_absolute_path_rejected(self, abs_path):
        """GIVEN an absolute volume_path
        WHEN creating an ImageArtifact
        THEN validation rejects with error.code = 'invalid_artifact'.
        """
        with pytest.raises(ValidationError) as exc_info:
            ImageArtifact(
                volume_path=abs_path,
                media_type="image/png",
            )
        error_msg = str(exc_info.value)
        assert "invalid_artifact" in error_msg or "volume_path" in error_msg

    def test_relative_path_accepted(self):
        """GIVEN a relative volume_path within the artifact namespace
        WHEN creating an ImageArtifact
        THEN validation succeeds.
        """
        artifact = ImageArtifact(
            volume_path="output/job-999/result.png",
            media_type="image/png",
        )
        assert artifact.volume_path == "output/job-999/result.png"


class TestBaseAtomicFlow:
    """Unit tests for BaseAtomicFlow validation."""

    def test_valid_flow(self):
        """GIVEN a valid flow with all required fields
        WHEN creating a BaseAtomicFlow
        THEN the model validates successfully.
        """
        flow = BaseAtomicFlow(
            workflow_name="test_flow",
            gpu_profile=GPUProfile.L4,
            timeout_s=300,
            prompt="a test prompt",
        )
        assert flow.workflow_name == "test_flow"
        assert flow.gpu_profile == GPUProfile.L4
        assert flow.timeout_s == 300
        assert flow.prompt == "a test prompt"

    def test_prompt_too_long_rejected(self):
        """GIVEN a prompt exceeding 4000 characters
        WHEN creating a BaseAtomicFlow
        THEN validation rejects with max_length.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                gpu_profile=GPUProfile.L4,
                timeout_s=300,
                prompt="x" * 4001,
            )

    def test_prompt_at_max_length_accepted(self):
        """GIVEN a prompt exactly at 4000 characters
        WHEN creating a BaseAtomicFlow
        THEN the model validates successfully.
        """
        flow = BaseAtomicFlow(
            workflow_name="test_flow",
            gpu_profile=GPUProfile.L4,
            timeout_s=300,
            prompt="x" * 4000,
        )
        assert flow.prompt == "x" * 4000

    def test_empty_prompt_rejected(self):
        """GIVEN an empty prompt
        WHEN creating a BaseAtomicFlow
        THEN validation rejects with min_length.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                gpu_profile=GPUProfile.L4,
                timeout_s=300,
                prompt="",
            )

    def test_missing_workflow_name_rejected(self):
        """GIVEN a subclass omits workflow_name
        WHEN the model is validated
        THEN Pydantic raises a validation error.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                gpu_profile=GPUProfile.L4,
                timeout_s=300,
                prompt="prompt",
            )

    def test_missing_gpu_profile_rejected(self):
        """GIVEN no gpu_profile
        WHEN creating a BaseAtomicFlow
        THEN validation fails.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                timeout_s=300,
                prompt="prompt",
            )

    def test_negative_timeout_rejected(self):
        """GIVEN a negative timeout_s
        WHEN creating a BaseAtomicFlow
        THEN validation fails.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                gpu_profile=GPUProfile.L4,
                timeout_s=-1,
                prompt="prompt",
            )

    def test_extra_fields_rejected(self):
        """GIVEN a BaseAtomicFlow with an unknown field
        WHEN creating with extra='forbid'
        THEN validation rejects the unknown field.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                gpu_profile=GPUProfile.L4,
                timeout_s=300,
                prompt="a test prompt",
                use_turbo=True,
            )

    def test_cannot_override_fixed_fields(self):
        """GIVEN a BaseAtomicFlow subclass with fixed defaults
        WHEN attempting to override a fixed field
        THEN validation rejects the override.
        """
        with pytest.raises(ValidationError):
            BaseAtomicFlow(
                workflow_name="test_flow",
                gpu_profile=GPUProfile.L4,
                timeout_s=300,
                prompt="prompt",
                unknown_field="should_fail",
            )


class TestFlowOutput:
    """Unit tests for FlowOutput contract."""

    def test_valid_flow_output_with_artifacts(self):
        """GIVEN a completed flow
        WHEN building FlowOutput
        THEN artifacts list contains one or more valid ImageArtifact entries.
        """
        output = FlowOutput(
            job_id="job-123",
            artifacts=[
                ImageArtifact(
                    volume_path="output/job-123/result.png",
                    media_type="image/png",
                ),
            ],
        )
        assert output.job_id == "job-123"
        assert len(output.artifacts) == 1
        assert output.artifacts[0].media_type == "image/png"

    def test_flow_output_must_have_at_least_one_artifact(self):
        """GIVEN a FlowOutput with empty artifacts
        WHEN validated
        THEN the model rejects with min_length.
        """
        with pytest.raises(ValidationError):
            FlowOutput(
                job_id="job-123",
                artifacts=[],
            )

    def test_missing_job_id_rejected(self):
        """GIVEN a FlowOutput without job_id
        WHEN validated
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            FlowOutput(
                artifacts=[
                    ImageArtifact(
                        volume_path="output/job-1/file.png",
                    ),
                ],
            )


class TestValidateArtifactOwnership:
    """Unit tests for _validate_artifact_ownership session validation."""

    def test_matching_session_accepted(self):
        """GIVEN an input artifact with owner_session_id matching the request session
        WHEN _validate_artifact_ownership is called
        THEN validation passes.
        """
        art = ImageArtifact(
            volume_path="input/session-abc/face.png",
            media_type="image/png",
            owner_session_id="session-abc",
        )
        # Should not raise
        _validate_artifact_ownership(art, "session-abc")

    def test_mismatched_session_rejected(self):
        """GIVEN an input artifact with owner_session_id different from the request session
        WHEN _validate_artifact_ownership is called
        THEN ValueError is raised with invalid_artifact.
        """
        art = ImageArtifact(
            volume_path="input/session-abc/face.png",
            media_type="image/png",
            owner_session_id="session-abc",
        )
        with pytest.raises(ValueError) as exc_info:
            _validate_artifact_ownership(art, "session-xyz")
        assert "invalid_artifact" in str(exc_info.value)
        assert "session-abc" in str(exc_info.value)
        assert "session-xyz" in str(exc_info.value)

    def test_no_owner_session_id_accepted(self):
        """GIVEN an input artifact without owner_session_id
        WHEN _validate_artifact_ownership is called
        THEN validation passes (backward compatibility).
        """
        art = ImageArtifact(
            volume_path="input/session-abc/face.png",
            media_type="image/png",
        )
        # Should not raise (backward compat)
        _validate_artifact_ownership(art, "session-abc")

    def test_chained_artifact_always_accepted(self):
        """GIVEN a chained artifact with source_job_id and a non-matching session
        WHEN _validate_artifact_ownership is called
        THEN validation passes (ownership propagates from source job).
        """
        art = ImageArtifact(
            volume_path="output/source-job/result.png",
            media_type="image/png",
            source_job_id="source-job-123",
            owner_session_id="session-abc",
        )
        # Should not raise — chained artifacts inherit ownership
        _validate_artifact_ownership(art, "session-xyz")
