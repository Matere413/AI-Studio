"""Unit tests for workflow templates and manifests."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import yaml
import pytest

from src.shared.workflows.models import ManifestSchema, NodeMapping
from src.shared.workflows.engine import WorkflowEngine
from src.shared.modal_config import default_whitelist


REALISTIC_PERSONA_CHECKPOINT = "RealVisXL_V4.0.safetensors"
FACEID_ADAPTER = "ip-adapter-faceid-plusv2_sdxl.bin"
CLIP_VISION_MODEL = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
CHECKPOINT_LOADER_COMPATIBLE_DEFAULTS = {REALISTIC_PERSONA_CHECKPOINT}
QWEN_UNET = "qwen_image_2512_fp8_e4m3fn.safetensors"
QWEN_CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
QWEN_VAE = "qwen_image_vae.safetensors"


class TestTxt2imgWorkflow:
    """Unit tests for txt2img workflow template and manifest."""

    def test_workflow_json_exists(self):
        """GIVEN the txt2img workflow directory
        WHEN checking for workflow.json
        THEN the file exists and is valid JSON.
        """
        workflow_path = Path("src/workflows/txt2img/workflow.json")
        assert workflow_path.exists(), "workflow.json not found"

        with open(workflow_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "prompt" in data

    def test_manifest_yaml_exists(self):
        """GIVEN the txt2img workflow directory
        WHEN checking for manifest.yaml
        THEN the file exists and is valid YAML.
        """
        manifest_path = Path("src/workflows/txt2img/manifest.yaml")
        assert manifest_path.exists(), "manifest.yaml not found"

        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "inputs" in data

    def test_manifest_validates(self):
        """GIVEN the txt2img manifest.yaml
        WHEN loading it into ManifestSchema
        THEN the schema validates successfully.
        """
        manifest_path = Path("src/workflows/txt2img/manifest.yaml")
        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        # Parse raw dict into ManifestSchema
        inputs = {
            k: NodeMapping(**v)
            for k, v in raw["inputs"].items()
        }
        manifest = ManifestSchema(inputs=inputs)

        # Assert expected mappings
        assert "prompt" in manifest.inputs
        assert manifest.inputs["prompt"].node_id == "6"
        assert manifest.inputs["prompt"].field == "text"

        assert "negative_prompt" in manifest.inputs
        assert manifest.inputs["negative_prompt"].node_id == "7"
        assert manifest.inputs["negative_prompt"].field == "text"

        assert "checkpoint" in manifest.inputs
        assert manifest.inputs["checkpoint"].node_id == "4"
        assert manifest.inputs["checkpoint"].field == "ckpt_name"

    def test_manifest_references_valid_nodes(self):
        """GIVEN the txt2img workflow and manifest
        WHEN cross-referencing node IDs
        THEN all manifest node IDs exist in the workflow template.
        """
        workflow_path = Path("src/workflows/txt2img/workflow.json")
        manifest_path = Path("src/workflows/txt2img/manifest.yaml")

        with open(workflow_path) as f:
            workflow = json.load(f)
        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        workflow_nodes = workflow["prompt"]
        for key, mapping in raw["inputs"].items():
            node_id = mapping["node_id"]
            assert node_id in workflow_nodes, f"Manifest input '{key}' references missing node '{node_id}'"
            field = mapping["field"]
            assert field in workflow_nodes[node_id]["inputs"], f"Manifest input '{key}' references missing field '{field}' in node '{node_id}'"


class TestRealisticPersonaWorkflow:
    """Unit tests for the realistic_persona workflow assets."""

    def test_workflow_json_uses_identity_preservation_node_graph(self):
        """GIVEN the realistic_persona workflow directory
        WHEN loading workflow.json
        THEN it contains FaceID Plus V2 identity nodes wired into sampling.
        """
        workflow_path = Path("src/workflows/realistic_persona/workflow.json")
        assert workflow_path.exists(), "realistic_persona workflow.json not found"

        with open(workflow_path) as f:
            workflow = json.load(f)

        node_classes = {
            node["class_type"]
            for node in workflow["prompt"].values()
        }
        assert node_classes == {
            "CheckpointLoaderSimple",
            "EmptyLatentImage",
            "CLIPTextEncode",
            "LoadImageFromBase64",
            "IPAdapterModelLoader",
            "CLIPVisionLoader",
            "IPAdapterFaceIDPlusV2",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        }
        assert "FaceDetailer" not in node_classes
        assert "InstantID" not in " ".join(node_classes)
        assert workflow["prompt"]["3"]["inputs"]["model"] == ["12", 0]
        assert workflow["prompt"]["11"]["inputs"]["ipadapter_file"] == FACEID_ADAPTER
        assert workflow["prompt"]["13"]["inputs"]["clip_name"] == CLIP_VISION_MODEL

    def test_manifest_yaml_declares_persona_controls_defaults_and_templates(self):
        """GIVEN the realistic_persona manifest
        WHEN loading manifest.yaml
        THEN it declares persona controls, defaults, output types, and prompt templates.
        """
        manifest_path = Path("src/workflows/realistic_persona/manifest.yaml")
        assert manifest_path.exists(), "realistic_persona manifest.yaml not found"

        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        manifest = ManifestSchema.model_validate(raw)

        expected_controls = [
            "age",
            "gender",
            "ethnicity",
            "wardrobe",
            "expression",
            "background",
        ]
        assert manifest.default_checkpoint == REALISTIC_PERSONA_CHECKPOINT
        assert set(expected_controls + [
            "prompt",
            "negative_prompt",
            "output_type",
            "image_url",
            "faceid_strength",
        ]).issubset(
            manifest.inputs
        )
        assert manifest.inputs["image_url"].node_id == "10"
        assert manifest.inputs["image_url"].field == "image_url"
        assert manifest.inputs["faceid_strength"].node_id == "12"
        assert manifest.inputs["faceid_strength"].field == "strength"
        assert manifest.defaults["checkpoint"] == REALISTIC_PERSONA_CHECKPOINT
        assert manifest.defaults["faceid_strength"] == 0
        assert manifest.defaults["output_type"] == "portrait"
        assert manifest.prompt_templates["prompt"].count("{") >= len(expected_controls)
        assert manifest.persona_metadata["controls"] == expected_controls
        assert manifest.persona_metadata["output_types"] == [
            "portrait",
            "full-body",
            "lifestyle",
            "editorial",
        ]
        assert "IPAdapter" not in manifest.persona_metadata["v1_excluded_nodes"]

    def test_realistic_persona_workflow_loads_and_resolves_default_prompt(self):
        """GIVEN realistic_persona workflow assets and an approved checkpoint
        WHEN the workflow engine applies only a prompt
        THEN manifest defaults produce a resolved graph with the locked checkpoint.
        """
        whitelist = json.dumps({"checkpoints": [REALISTIC_PERSONA_CHECKPOINT], "loras": []})

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/realistic_persona/workflow.json",
                manifest_path="src/workflows/realistic_persona/manifest.yaml",
            )

        resolved = engine.apply_parameters({"prompt": "editorial character study"})

        assert resolved["prompt"]["4"]["inputs"]["ckpt_name"] == REALISTIC_PERSONA_CHECKPOINT
        assert resolved["prompt"]["10"]["inputs"]["image_url"] == ""
        assert resolved["prompt"]["12"]["inputs"]["strength"] == 0
        assert "34-year-old" in resolved["prompt"]["6"]["inputs"]["text"]
        assert "editorial character study" in resolved["prompt"]["6"]["inputs"]["text"]
        assert "plastic skin" in resolved["prompt"]["7"]["inputs"]["text"]

    @pytest.mark.parametrize(
        ("faceid_strength", "image_url"),
        [
            (0, ""),
            (0.75, "data:image/png;base64,aGVsbG8="),
        ],
    )
    def test_realistic_persona_workflow_resolves_identity_inputs(self, faceid_strength, image_url):
        """GIVEN realistic_persona workflow assets and an approved checkpoint
        WHEN resolving prompt-only and identity-conditioned parameters
        THEN the workflow injects image_url and FaceID strength into the graph.
        """
        whitelist = json.dumps({"checkpoints": [REALISTIC_PERSONA_CHECKPOINT], "loras": []})

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/realistic_persona/workflow.json",
                manifest_path="src/workflows/realistic_persona/manifest.yaml",
            )

        resolved = engine.apply_parameters({
            "prompt": "editorial character study",
            "image_url": image_url,
            "faceid_strength": faceid_strength,
        })

        assert resolved["prompt"]["10"]["inputs"]["image_url"] == image_url
        assert resolved["prompt"]["12"]["inputs"]["strength"] == faceid_strength
        assert resolved["prompt"]["12"]["inputs"]["model"] == ["4", 0]
        assert resolved["prompt"]["3"]["inputs"]["model"] == ["12", 0]

    def test_realistic_persona_default_checkpoint_is_whitelisted_and_loader_compatible(self):
        """GIVEN the realistic_persona manifest default
        WHEN checking runtime model constraints
        THEN it uses a whitelisted complete checkpoint compatible with CheckpointLoaderSimple.
        """
        manifest_path = Path("src/workflows/realistic_persona/manifest.yaml")

        with open(manifest_path) as f:
            manifest = ManifestSchema.model_validate(yaml.safe_load(f))

        whitelist = json.loads(default_whitelist)

        assert manifest.default_checkpoint in whitelist["checkpoints"]
        assert manifest.default_checkpoint in CHECKPOINT_LOADER_COMPATIBLE_DEFAULTS


class TestQwenTxt2ImgWorkflow:
    """Unit tests for the qwen_txt2img workflow assets."""

    def test_qwen_workflow_json_uses_standard_comfy_nodes_without_switch_nodes(self):
        """GIVEN the qwen_txt2img workflow directory
        WHEN loading workflow.json
        THEN it is prompt-wrapped and contains no custom switch/primitive nodes.
        """
        workflow_path = Path("src/workflows/qwen_txt2img/workflow.json")
        assert workflow_path.exists(), "qwen_txt2img workflow.json not found"

        with open(workflow_path) as f:
            workflow = json.load(f)

        node_classes = {node["class_type"] for node in workflow["prompt"].values()}
        assert {
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "ModelSamplingAuraFlow",
            "EmptySD3LatentImage",
            "CLIPTextEncode",
            "KSampler",
            "VAEDecode",
            "SaveImage",
        }.issubset(node_classes)
        assert "ComfySwitchNode" not in node_classes
        assert "PrimitiveBoolean" not in node_classes
        assert "PrimitiveInt" not in node_classes
        assert "PrimitiveFloat" not in node_classes

    def test_qwen_manifest_declares_runtime_inputs_and_defaults(self):
        """GIVEN the qwen_txt2img manifest
        WHEN loading manifest.yaml
        THEN it declares Qwen controls and high-quality defaults.
        """
        manifest_path = Path("src/workflows/qwen_txt2img/manifest.yaml")
        assert manifest_path.exists(), "qwen_txt2img manifest.yaml not found"

        with open(manifest_path) as f:
            raw = yaml.safe_load(f)

        manifest = ManifestSchema.model_validate(raw)
        expected_inputs = {
            "prompt",
            "negative_prompt",
            "width",
            "height",
            "steps",
            "cfg",
            "sampler_name",
            "sampler_scheduler",
            "unet",
            "clip",
            "vae",
        }

        assert expected_inputs.issubset(manifest.inputs)
        assert manifest.defaults["width"] == 1024
        assert manifest.defaults["height"] == 1024
        assert manifest.defaults["quality_mode"] == "high"
        assert manifest.defaults["steps"] == 50
        assert manifest.defaults["cfg"] == 7.0
        assert manifest.defaults["sampler_name"] == "euler_ancestral"
        assert manifest.defaults["sampler_scheduler"] == "normal"
        assert manifest.defaults["unet"] == QWEN_UNET
        assert manifest.defaults["clip"] == QWEN_CLIP
        assert manifest.defaults["vae"] == QWEN_VAE

    def test_qwen_manifest_references_valid_workflow_fields(self):
        """GIVEN Qwen workflow assets
        WHEN creating WorkflowEngine
        THEN manifest node and field references validate successfully.
        """
        whitelist = json.dumps({"unets": [QWEN_UNET], "clip": [QWEN_CLIP], "vae": [QWEN_VAE], "loras": []})

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/qwen_txt2img/workflow.json",
                manifest_path="src/workflows/qwen_txt2img/manifest.yaml",
            )

        resolved = engine.apply_parameters(
            {
                "prompt": "a precision watch on marble",
                "negative_prompt": "text, watermark",
                "width": 1280,
                "height": 768,
            }
        )

        assert resolved["prompt"]["7"]["inputs"]["text"] == "a precision watch on marble"
        assert resolved["prompt"]["8"]["inputs"]["text"] == "text, watermark"
        assert resolved["prompt"]["5"]["inputs"]["width"] == 1280
        assert resolved["prompt"]["5"]["inputs"]["height"] == 768
