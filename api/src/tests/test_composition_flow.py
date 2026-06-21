"""Unit tests for CompositionRequest, CompositionFlow, and composition workflow assets."""

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.shared.flows.base import GPUProfile, ImageArtifact
from src.shared.flows.composition import CompositionFlow, CompositionRequest
from src.shared.workflows.models import ManifestSchema


BASE_REQUEST = {
    "workflow_name": "composition",
    "gpu_profile": "L4",
    "timeout_s": 600,
}


class TestCompositionRequest:
    """Unit tests for CompositionRequest validation."""

    def test_valid_composition_request(self):
        """GIVEN a valid composition request with both images and control_mode
        WHEN creating CompositionRequest
        THEN the model validates successfully.
        """
        request = CompositionRequest(
            **BASE_REQUEST,
            background_image=ImageArtifact(
                volume_path="input/background.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/foreground.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose subject onto background",
        )
        assert request.background_image.volume_path == "input/background.png"
        assert request.foreground_image.volume_path == "input/foreground.png"
        assert request.control_mode == "depth"
        assert request.control_strength == 1.0
        assert request.seed is None
        assert request.prompt == "compose subject onto background"

    def test_canny_control_mode_accepted(self):
        """GIVEN a composition request with control_mode = "canny"
        WHEN validated
        THEN the model accepts it.
        """
        request = CompositionRequest(
            **BASE_REQUEST,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="canny",
            prompt="compose with canny edges",
        )
        assert request.control_mode == "canny"

    def test_invalid_control_mode_rejected(self):
        """GIVEN a composition request with control_mode = "pose"
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError, match="control_mode"):
            CompositionRequest(
                **BASE_REQUEST,
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="pose",
                prompt="compose with invalid control",
            )

    def test_missing_background_image_rejected(self):
        """GIVEN a composition request without background_image
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError):
            CompositionRequest(
                **BASE_REQUEST,
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                prompt="missing background",
            )

    def test_missing_foreground_image_rejected(self):
        """GIVEN a composition request without foreground_image
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError):
            CompositionRequest(
                **BASE_REQUEST,
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                prompt="missing foreground",
            )

    @pytest.mark.parametrize(
        "invalid_strength",
        [-0.1, 2.1, 999],
    )
    def test_control_strength_out_of_bounds_rejected(self, invalid_strength):
        """GIVEN a control_strength outside [0.0, 2.0]
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError):
            CompositionRequest(
                **BASE_REQUEST,
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                control_strength=invalid_strength,
                prompt="invalid strength",
            )

    @pytest.mark.parametrize(
        "valid_strength",
        [0.0, 0.5, 1.0, 1.5, 2.0],
    )
    def test_control_strength_valid_bounds(self, valid_strength):
        """GIVEN a control_strength within [0.0, 2.0]
        WHEN validated
        THEN the model accepts it.
        """
        request = CompositionRequest(
            **BASE_REQUEST,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            control_strength=valid_strength,
            prompt="valid strength",
        )
        assert request.control_strength == valid_strength

    def test_seed_accepted(self):
        """GIVEN a composition request with an explicit seed
        WHEN validated
        THEN seed is preserved.
        """
        request = CompositionRequest(
            **BASE_REQUEST,
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            seed=42,
            prompt="seeded composition",
        )
        assert request.seed == 42

    def test_extra_fields_rejected(self):
        """GIVEN CompositionRequest with an unknown field
        WHEN validated with extra='forbid'
        THEN the model rejects the unknown field.
        """
        with pytest.raises(ValidationError):
            CompositionRequest(
                **BASE_REQUEST,
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                prompt="compose",
                use_turbo=True,
            )


class TestCompositionFlow:
    """Unit tests for CompositionFlow binding."""

    def test_flow_has_correct_workflow_name(self):
        """GIVEN CompositionFlow
        WHEN accessing workflow_name
        THEN it returns "composition".
        """
        flow = CompositionFlow(
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose",
        )
        assert flow.workflow_name == "composition"

    def test_flow_has_l4_gpu_profile(self):
        """GIVEN CompositionFlow
        THEN gpu_profile is L4.
        """
        flow = CompositionFlow(
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose",
        )
        assert flow.gpu_profile == GPUProfile.L4

    def test_flow_has_600s_timeout(self):
        """GIVEN CompositionFlow
        THEN timeout_s is 600.
        """
        flow = CompositionFlow(
            background_image=ImageArtifact(
                volume_path="input/bg.png",
                media_type="image/png",
            ),
            foreground_image=ImageArtifact(
                volume_path="input/fg.png",
                media_type="image/png",
            ),
            control_mode="depth",
            prompt="compose",
        )
        assert flow.timeout_s == 600

    def test_workflow_name_override_rejected(self):
        """GIVEN CompositionFlow constructed with a different workflow_name
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            CompositionFlow(
                workflow_name="txt2img",
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                prompt="compose",
            )

    def test_gpu_profile_override_rejected(self):
        """GIVEN CompositionFlow constructed with a different gpu_profile
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            CompositionFlow(
                gpu_profile="T4",
                background_image=ImageArtifact(
                    volume_path="input/bg.png",
                    media_type="image/png",
                ),
                foreground_image=ImageArtifact(
                    volume_path="input/fg.png",
                    media_type="image/png",
                ),
                control_mode="depth",
                prompt="compose",
            )


class TestCompositionWorkflowAssets:
    """Contract tests for composition workflow.json and manifest.yaml."""

    WORKFLOW_NAME = "composition"

    def test_workflow_assets_exist(self):
        """GIVEN the composition workflow name
        WHEN checking disk assets
        THEN both workflow.json and manifest.yaml exist.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")

        assert workflow_path.exists(), f"{self.WORKFLOW_NAME} workflow.json not found"
        assert manifest_path.exists(), f"{self.WORKFLOW_NAME} manifest.yaml not found"

    def test_workflow_has_prompt_key(self):
        """GIVEN the composition workflow.json
        WHEN loaded
        THEN it has a 'prompt' key.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        assert "prompt" in workflow

    def test_manifest_validates_as_manifest_schema(self):
        """GIVEN the composition manifest.yaml
        WHEN loaded as ManifestSchema
        THEN it validates without errors.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )
        assert manifest is not None

    def test_manifest_declares_prompt_input(self):
        """GIVEN the composition manifest
        THEN it declares 'prompt' input mapping.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "prompt" in manifest.inputs

        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        mapping = manifest.inputs["prompt"]
        node = workflow["prompt"][mapping.node_id]
        assert node["class_type"] in ("CLIPTextEncode",)

    def test_manifest_declares_background_image(self):
        """GIVEN the composition manifest
        THEN it declares background_image mapping to a LoadImage node.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "background_image" in manifest.inputs

        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        mapping = manifest.inputs["background_image"]
        node = workflow["prompt"][mapping.node_id]
        assert node["class_type"] in ("LoadImage",)

    def test_manifest_declares_foreground_image(self):
        """GIVEN the composition manifest
        THEN it declares foreground_image mapping to a LoadImage node.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "foreground_image" in manifest.inputs

        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        mapping = manifest.inputs["foreground_image"]
        node = workflow["prompt"][mapping.node_id]
        assert node["class_type"] in ("LoadImage",)

    def test_manifest_declares_control_mode(self):
        """GIVEN the composition manifest
        THEN it declares control_mode input mapping.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "control_mode" in manifest.inputs

    def test_manifest_declares_model_inputs(self):
        """GIVEN the composition manifest
        THEN it declares unet, clip, and vae model inputs.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        for model_key in ("unet", "clip", "vae"):
            assert model_key in manifest.inputs, (
                f"manifest should declare '{model_key}' input"
            )

    def test_manifest_has_model_defaults(self):
        """GIVEN the composition manifest
        THEN it provides default model filenames for unet, clip, and vae.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "unet" in manifest.defaults
        assert "clip" in manifest.defaults
        assert "vae" in manifest.defaults
