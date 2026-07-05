"""Unit tests for IdentityRequest, IdentityFlow, and identity workflow assets."""

import json
import os
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.shared.flows.base import GPUProfile, ImageArtifact
from src.shared.flows.identity import IdentityFlow, IdentityRequest
from src.shared.workflows.models import ManifestSchema


BASE_REQUEST = {
    "workflow_name": "identity",
    "gpu_profile": "A100",
    "timeout_s": 1200,
}


class TestIdentityRequest:
    """Unit tests for IdentityRequest validation."""

    def test_valid_identity_request(self):
        """GIVEN a valid identity request with reference_face
        WHEN creating IdentityRequest
        THEN the model validates successfully.
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        assert request.reference_face.volume_path == "input/reference.png"
        assert request.reference_face.media_type == "image/png"
        assert request.prompt == "identity preserving portrait"
        assert request.width == 1024
        assert request.height == 1024
        assert request.seed is None

    def test_missing_reference_face_rejected(self):
        """GIVEN an identity request without reference_face
        WHEN validated
        THEN the request is rejected.
        """
        with pytest.raises(ValidationError):
            IdentityRequest(
                **BASE_REQUEST,
                prompt="identity preserving portrait",
            )

    def test_webp_source_media_type_accepted(self):
        """GIVEN reference_face.media_type = "image/webp"
        WHEN validated
        THEN the request is accepted (image/webp is now a supported type).
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.webp",
                media_type="image/webp",
            ),
            prompt="identity preserving portrait",
        )
        assert request.reference_face.media_type == "image/webp"

    def test_custom_dimensions_accepted(self):
        """GIVEN an identity request with custom width/height
        WHEN validated
        THEN dimensions are preserved.
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            width=768,
            height=1024,
            prompt="identity preserving portrait",
        )
        assert request.width == 768
        assert request.height == 1024

    @pytest.mark.parametrize("bad_dim", [65, 100, 200])
    def test_width_not_multiple_of_64_rejected(self, bad_dim):
        """GIVEN a width that passes ge=64 but is not a multiple of 64
        WHEN validated
        THEN the request is rejected with the multiple-of-64 message.
        """
        with pytest.raises(ValidationError) as exc_info:
            IdentityRequest(
                **BASE_REQUEST,
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                width=bad_dim,
                height=1024,
                prompt="identity preserving portrait",
            )
        assert "must be a multiple of 64" in str(exc_info.value)

    @pytest.mark.parametrize("bad_dim", [1, 32, 63])
    def test_width_below_minimum_rejected(self, bad_dim):
        """GIVEN a width below the minimum of 64
        WHEN validated
        THEN the request is rejected with greater-than-or-equal message.
        """
        with pytest.raises(ValidationError) as exc_info:
            IdentityRequest(
                **BASE_REQUEST,
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                width=bad_dim,
                height=1024,
                prompt="identity preserving portrait",
            )
        assert "greater than or equal to 64" in str(exc_info.value)

    @pytest.mark.parametrize("bad_dim", [65, 100, 200])
    def test_height_not_multiple_of_64_rejected(self, bad_dim):
        """GIVEN a height that passes ge=64 but is not a multiple of 64
        WHEN validated
        THEN the request is rejected with the multiple-of-64 message.
        """
        with pytest.raises(ValidationError) as exc_info:
            IdentityRequest(
                **BASE_REQUEST,
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                width=1024,
                height=bad_dim,
                prompt="identity preserving portrait",
            )
        assert "must be a multiple of 64" in str(exc_info.value)

    @pytest.mark.parametrize("bad_dim", [1, 32, 63])
    def test_height_below_minimum_rejected(self, bad_dim):
        """GIVEN a height below the minimum of 64
        WHEN validated
        THEN the request is rejected with greater-than-or-equal message.
        """
        with pytest.raises(ValidationError) as exc_info:
            IdentityRequest(
                **BASE_REQUEST,
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                width=1024,
                height=bad_dim,
                prompt="identity preserving portrait",
            )
        assert "greater than or equal to 64" in str(exc_info.value)

    @pytest.mark.parametrize("valid_dim", [64, 128, 512, 1024, 2048])
    def test_valid_dimensions_accepted(self, valid_dim):
        """GIVEN valid dimensions that are multiples of 64
        WHEN validated
        THEN the model accepts them.
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            width=valid_dim,
            height=valid_dim,
            prompt="identity preserving portrait",
        )
        assert request.width == valid_dim
        assert request.height == valid_dim

    def test_seed_accepted(self):
        """GIVEN an identity request with an explicit seed
        WHEN validated
        THEN seed is preserved.
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            seed=42,
            prompt="seeded identity",
        )
        assert request.seed == 42

    def test_seed_negative_one_accepted(self):
        """GIVEN an identity request with seed = -1
        WHEN validated
        THEN -1 seed is accepted.
        """
        request = IdentityRequest(
            **BASE_REQUEST,
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            seed=-1,
            prompt="identity with random seed",
        )
        assert request.seed == -1

    def test_extra_fields_rejected(self):
        """GIVEN IdentityRequest with an unknown field
        WHEN validated with extra='forbid'
        THEN the model rejects the unknown field.
        """
        with pytest.raises(ValidationError):
            IdentityRequest(
                **BASE_REQUEST,
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                prompt="identity",
                use_turbo=True,
            )


class TestIdentityFlow:
    """Unit tests for IdentityFlow binding."""

    def test_flow_has_correct_workflow_name(self):
        """GIVEN IdentityFlow
        WHEN accessing workflow_name
        THEN it returns "identity".
        """
        flow = IdentityFlow(
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        assert flow.workflow_name == "identity"

    def test_flow_has_a100_gpu_profile(self):
        """GIVEN IdentityFlow
        THEN gpu_profile is A100.
        """
        flow = IdentityFlow(
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        assert flow.gpu_profile == GPUProfile.A100

    def test_flow_has_1200s_timeout(self):
        """GIVEN IdentityFlow
        THEN timeout_s is 1200.
        """
        flow = IdentityFlow(
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        assert flow.timeout_s == 1200

    def test_workflow_name_override_rejected(self):
        """GIVEN IdentityFlow constructed with a different workflow_name
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            IdentityFlow(
                workflow_name="txt2img",
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                prompt="identity preserving portrait",
            )

    def test_gpu_profile_override_rejected(self):
        """GIVEN IdentityFlow constructed with a different gpu_profile
        WHEN validated
        THEN the override is rejected.
        """
        with pytest.raises(ValidationError):
            IdentityFlow(
                gpu_profile="L4",
                reference_face=ImageArtifact(
                    volume_path="input/reference.png",
                    media_type="image/png",
                ),
                prompt="identity preserving portrait",
            )

    def test_default_dimensions_are_1024(self):
        """GIVEN IdentityFlow without explicit dimensions
        WHEN validated
        THEN width and height default to 1024.
        """
        flow = IdentityFlow(
            reference_face=ImageArtifact(
                volume_path="input/reference.png",
                media_type="image/png",
            ),
            prompt="identity preserving portrait",
        )
        assert flow.width == 1024
        assert flow.height == 1024


class TestIdentityWorkflowAssets:
    """Contract tests for identity workflow.json and manifest.yaml."""

    WORKFLOW_NAME = "identity"

    def test_workflow_assets_exist(self):
        """GIVEN the identity workflow name
        WHEN checking disk assets
        THEN both workflow.json and manifest.yaml exist.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")

        assert workflow_path.exists(), f"{self.WORKFLOW_NAME} workflow.json not found"
        assert manifest_path.exists(), f"{self.WORKFLOW_NAME} manifest.yaml not found"

    def test_workflow_has_prompt_key(self):
        """GIVEN the identity workflow.json
        WHEN loaded
        THEN it has a 'prompt' key.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        assert "prompt" in workflow

    def test_manifest_validates_as_manifest_schema(self):
        """GIVEN the identity manifest.yaml
        WHEN loaded as ManifestSchema
        THEN it validates without errors.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )
        assert manifest is not None

    def test_manifest_declares_reference_face(self):
        """GIVEN the identity manifest
        THEN it declares reference_face mapping to a LoadImage node.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "reference_face" in manifest.inputs

        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())
        mapping = manifest.inputs["reference_face"]
        node = workflow["prompt"][mapping.node_id]
        assert node["class_type"] in ("LoadImage",)

    def test_manifest_declares_prompt_input(self):
        """GIVEN the identity manifest
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

    def test_manifest_declares_model_inputs(self):
        """GIVEN the identity manifest
        THEN it declares unet, clip, vae, pulid, and face_detector model inputs.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        for model_key in ("unet", "clip", "vae", "pulid", "face_detector"):
            assert model_key in manifest.inputs, (
                f"manifest should declare '{model_key}' input"
            )

    def test_manifest_has_model_defaults(self):
        """GIVEN the identity manifest
        THEN it provides default model filenames.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "unet" in manifest.defaults
        assert "clip" in manifest.defaults
        assert "vae" in manifest.defaults
        assert "pulid" in manifest.defaults
        assert "face_detector" in manifest.defaults

    def test_workflow_has_pulid_nodes(self):
        """GIVEN the identity workflow.json
        THEN it contains PuLID Flux nodes for identity preservation.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        # Verify ApplyPulidFlux node exists
        apply_node = workflow["prompt"].get("10")
        assert apply_node is not None, "Node 10 (ApplyPulidFlux) must exist"
        assert apply_node["class_type"] == "ApplyPulidFlux"

        # Verify PuLID model loader
        loader_node = workflow["prompt"].get("16")
        assert loader_node is not None, "Node 16 (PulidFluxModelLoader) must exist"
        assert loader_node["class_type"] == "PulidFluxModelLoader"

    def test_apply_pulid_face_analysis_wired_to_insight_face_loader(self):
        """GIVEN the identity workflow.json
        WHEN inspecting ApplyPulidFlux (node 10) face_analysis input
        THEN it is wired to node 12 (PulidFluxInsightFaceLoader), which
        emits FACEANALYSIS — not to node 11 (KSampler), which emits LATENT.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        apply_node = workflow["prompt"]["10"]
        assert apply_node["class_type"] == "ApplyPulidFlux"

        face_analysis_ref = apply_node["inputs"]["face_analysis"]
        source_node_id = face_analysis_ref[0]
        assert source_node_id == "12", (
            "ApplyPulidFlux.face_analysis must reference node 12 "
            "(PulidFluxInsightFaceLoader, emits FACEANALYSIS); got "
            f"node {source_node_id}"
        )
        source_node = workflow["prompt"][source_node_id]
        assert source_node["class_type"] == "PulidFluxInsightFaceLoader", (
            "face_analysis source must be PulidFluxInsightFaceLoader, got "
            f"{source_node['class_type']}"
        )

    def test_ultralytics_detector_model_name_uses_bbox_path(self):
        """GIVEN the identity workflow.json
        WHEN inspecting UltralyticsDetectorProvider (node 13) model_name
        THEN it uses the Impact Pack 'bbox/...' dropdown path, matching the
        symlinked location under models/ultralytics/bbox/.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        detector_node = workflow["prompt"]["13"]
        assert detector_node["class_type"] == "UltralyticsDetectorProvider"
        model_name = detector_node["inputs"]["model_name"]
        assert model_name.startswith("bbox/"), (
            "UltralyticsDetectorProvider.model_name must use the 'bbox/...' "
            f"dropdown path expected by Impact Pack, got '{model_name}'"
        )
        assert os.path.basename(model_name) == "face_yolov8m.pt", (
            "face detector file must remain face_yolov8m.pt, got "
            f"{os.path.basename(model_name)}"
        )

    def test_workflow_ksampler_seed_is_non_negative(self):
        """GIVEN the identity workflow.json
        WHEN inspecting every node's 'seed' input
        THEN no seed is negative (ComfyUI validates KSampler seed min=0).
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        for node_id, node in workflow["prompt"].items():
            seed = node.get("inputs", {}).get("seed")
            if seed is not None:
                assert seed >= 0, (
                    f"Node {node_id} ({node['class_type']}) seed must be "
                    f"non-negative for ComfyUI validation, got {seed}"
                )

    def test_manifest_seed_default_is_non_negative(self):
        """GIVEN the identity manifest.yaml
        THEN the default seed is non-negative (ComfyUI validates min=0)."""
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "seed" in manifest.defaults
        assert manifest.defaults["seed"] >= 0, (
            "manifest default seed must be non-negative for ComfyUI validation, "
            f"got {manifest.defaults['seed']}"
        )

    def test_workflow_uses_unetloader_not_gguf(self):
        """GIVEN the identity workflow.json
        THEN it loads the UNet via UNETLoader (not UnetLoaderGGUF).
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        unet_node_id = None
        for nid, node in workflow["prompt"].items():
            if node["class_type"] == "UNETLoader":
                unet_node_id = nid
                break
        assert unet_node_id is not None, (
            "Workflow must have a UNETLoader node (not UnetLoaderGGUF)"
        )
        # Verify it's NOT a GGUF loader
        for nid, node in workflow["prompt"].items():
            assert node["class_type"] != "UnetLoaderGGUF", (
                "GGUF UnetLoader must NOT be used in new identity workflow"
            )

    def test_workflow_has_facedetailer(self):
        """GIVEN the identity workflow.json
        THEN it contains a FaceDetailer node for face enhancement.
        """
        workflow_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/workflow.json")
        workflow = json.loads(workflow_path.read_text())

        fd_node = workflow["prompt"].get("14")
        assert fd_node is not None, "Node 14 (FaceDetailer) must exist"
        assert fd_node["class_type"] == "FaceDetailer"

    def test_manifest_declares_seed_input(self):
        """GIVEN the identity manifest
        THEN it declares 'seed' input mapping.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "seed" in manifest.inputs

    def test_manifest_has_seed_default(self):
        """GIVEN the identity manifest
        THEN it provides a default seed value.
        """
        manifest_path = Path(f"src/workflows/{self.WORKFLOW_NAME}/manifest.yaml")
        manifest = ManifestSchema.model_validate(
            yaml.safe_load(manifest_path.read_text())
        )

        assert "seed" in manifest.defaults
