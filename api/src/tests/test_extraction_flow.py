"""Unit tests for ExtractionRequest, ExtractionFlow, and extraction workflow assets."""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.shared.flows.base import GPUProfile, ImageArtifact
from src.shared.flows.extraction import ExtractionFlow, ExtractionRequest
from src.shared.workflows.models import ManifestSchema


BASE_REQUEST = {
    "workflow_name": "extraction",
    "gpu_profile": "L4",
    "timeout_s": 300,
}


class TestExtractionRequest:
    """Unit tests for ExtractionRequest validation."""

    def test_valid_extraction_request(self):
        """GIVEN a valid extraction request with input_image
        WHEN creating ExtractionRequest
        THEN the model validates successfully.
        """
        request = ExtractionRequest(
            **BASE_REQUEST,
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        assert request.input_image.volume_path == "input/source.png"
        assert request.input_image.media_type == "image/png"
        assert request.prompt == "extract foreground"

    def test_missing_input_image_rejected(self):
        """GIVEN an extraction request without input_image
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError):
            ExtractionRequest(
                **BASE_REQUEST,
                prompt="extract foreground",
            )

    def test_webp_source_media_type_accepted(self):
        """GIVEN input_image.media_type = "image/webp"
        WHEN validated
        THEN the request is accepted (image/webp is now a supported type).
        """
        request = ExtractionRequest(
            **BASE_REQUEST,
            input_image=ImageArtifact(
                volume_path="input/source.webp",
                media_type="image/webp",
            ),
            prompt="extract foreground",
        )
        assert request.input_image.media_type == "image/webp"

    def test_optional_mask_margin(self):
        """GIVEN an extraction request with optional mask_margin
        WHEN validated
        THEN mask_margin is preserved.
        """
        request = ExtractionRequest(
            **BASE_REQUEST,
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            mask_margin=5,
            prompt="extract foreground",
        )
        assert request.mask_margin == 5

    def test_mask_margin_default_none(self):
        """GIVEN an extraction request without mask_margin
        WHEN validated
        THEN mask_margin defaults to None.
        """
        request = ExtractionRequest(
            **BASE_REQUEST,
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        assert request.mask_margin is None


class TestExtractionFlow:
    """Unit tests for ExtractionFlow binding."""

    def test_flow_has_correct_workflow_name(self):
        """GIVEN ExtractionFlow
        WHEN accessing workflow_name
        THEN it returns "extraction".
        """
        flow = ExtractionFlow(
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        assert flow.workflow_name == "extraction"

    def test_flow_has_l4_gpu_profile(self):
        """GIVEN ExtractionFlow
        THEN gpu_profile is L4.
        """
        flow = ExtractionFlow(
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        assert flow.gpu_profile == GPUProfile.L4

    def test_flow_has_300s_timeout(self):
        """GIVEN ExtractionFlow
        THEN timeout_s is 300.
        """
        flow = ExtractionFlow(
            input_image=ImageArtifact(
                volume_path="input/source.png",
                media_type="image/png",
            ),
            prompt="extract foreground",
        )
        assert flow.timeout_s == 300

    def test_extra_fields_rejected_by_extraction_request(self):
        """GIVEN ExtractionRequest with an unknown field
        WHEN validated with extra='forbid'
        THEN the model rejects the unknown field.
        """
        with pytest.raises(ValidationError):
            ExtractionRequest(
                **BASE_REQUEST,
                input_image=ImageArtifact(
                    volume_path="input/source.png",
                    media_type="image/png",
                ),
                prompt="extract foreground",
                use_turbo=True,
            )

    def test_workflow_name_override_rejected(self):
        """GIVEN ExtractionFlow constructed with a different workflow_name
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            ExtractionFlow(
                workflow_name="txt2img",
                input_image=ImageArtifact(
                    volume_path="input/source.png",
                    media_type="image/png",
                ),
                prompt="extract foreground",
            )

    def test_gpu_profile_override_rejected(self):
        """GIVEN ExtractionFlow constructed with a different gpu_profile
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            ExtractionFlow(
                gpu_profile="T4",
                input_image=ImageArtifact(
                    volume_path="input/source.png",
                    media_type="image/png",
                ),
                prompt="extract foreground",
            )


class TestExtractionWorkflowAssets:
    """Contract tests for extraction workflow.json and manifest.yaml."""

    WORKFLOW_NAME = "extraction"

    def test_workflow_assets_exist(self):
        """GIVEN the extraction workflow name
        WHEN checking disk assets
        THEN both workflow.json and manifest.yaml exist.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")

        assert workflow_path.exists(), f"{self.WORKFLOW_NAME} workflow.json not found"
        assert manifest_path.exists(), f"{self.WORKFLOW_NAME} manifest.yaml not found"

    def test_workflow_has_prompt_key(self):
        """GIVEN the extraction workflow.json
        WHEN loaded
        THEN it has a 'prompt' key.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        assert "prompt" in workflow

    def test_manifest_validates_as_manifest_schema(self):
        """GIVEN the extraction manifest.yaml
        WHEN loaded as ManifestSchema
        THEN it validates without errors.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(yaml.safe_load(manifest_path.read_text()))
        assert manifest is not None

    def test_manifest_declares_input_image(self):
        """GIVEN the extraction manifest
        THEN it declares input_image mapping to a LoadImage node.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(yaml.safe_load(manifest_path.read_text()))

        assert "input_image" in manifest.inputs

        # Verify the referenced node exists in workflow and is LoadImage
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        mapping = manifest.inputs["input_image"]
        node = workflow["prompt"][mapping.node_id]
        assert node["class_type"] in ("LoadImage", "LoadImageFromBase64")

    def test_manifest_declares_output_artifact(self):
        """GIVEN the extraction manifest
        THEN it declares outputs.artifacts with extracted_image.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        raw = yaml.safe_load(manifest_path.read_text())

        assert "outputs" in raw
        assert "artifacts" in raw["outputs"]
        assert any(
            a.get("name") == "extracted_image"
            for a in raw["outputs"]["artifacts"]
        )

    def test_output_artifact_has_correct_media_type(self):
        """GIVEN the extracted_image output artifact
        THEN it declares media_type: image/png and has_alpha: true.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        raw = yaml.safe_load(manifest_path.read_text())

        for artifact in raw["outputs"]["artifacts"]:
            if artifact["name"] == "extracted_image":
                assert artifact["media_type"] == "image/png"
                assert artifact.get("has_alpha") is True
                return
        pytest.fail("extracted_image artifact not found in outputs")
