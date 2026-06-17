"""Unit tests for the WorkflowEngine."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.shared.workflows.engine import WorkflowEngine
from src.shared.workflows.models import NodeMapping, ManifestSchema


class TestWorkflowEngineInit:
    """Unit tests for WorkflowEngine initialization and validation."""

    def test_loads_valid_template_and_manifest(self):
        """GIVEN a valid template and manifest
        WHEN creating a WorkflowEngine
        THEN it loads successfully.
        """
        engine = WorkflowEngine(
            template_path="src/workflows/txt2img/workflow.json",
            manifest_path="src/workflows/txt2img/manifest.yaml",
        )
        assert engine.template is not None
        assert engine.manifest is not None
        assert "prompt" in engine.manifest.inputs

    def test_missing_template_raises(self):
        """GIVEN a missing template file
        WHEN creating a WorkflowEngine
        THEN FileNotFoundError is raised.
        """
        with pytest.raises(FileNotFoundError):
            WorkflowEngine(
                template_path="src/workflows/missing/workflow.json",
                manifest_path="src/workflows/txt2img/manifest.yaml",
            )

    def test_missing_manifest_raises(self):
        """GIVEN a missing manifest file
        WHEN creating a WorkflowEngine
        THEN FileNotFoundError is raised.
        """
        with pytest.raises(FileNotFoundError):
            WorkflowEngine(
                template_path="src/workflows/txt2img/workflow.json",
                manifest_path="src/workflows/missing/manifest.yaml",
            )

    def test_invalid_node_reference_raises(self):
        """GIVEN a manifest referencing a non-existent node
        WHEN creating a WorkflowEngine
        THEN ValueError is raised.
        """
        # Create a temporary manifest with a bad node reference
        bad_manifest = {
            "inputs": {
                "prompt": {"node_id": "999", "field": "text"}
            }
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(bad_manifest, f)
            manifest_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                WorkflowEngine(
                    template_path="src/workflows/txt2img/workflow.json",
                    manifest_path=manifest_path,
                )
            assert "missing node" in str(exc_info.value).lower()
        finally:
            os.unlink(manifest_path)

    def test_invalid_field_reference_raises(self):
        """GIVEN a manifest referencing a non-existent field
        WHEN creating a WorkflowEngine
        THEN ValueError is raised.
        """
        bad_manifest = {
            "inputs": {
                "prompt": {"node_id": "6", "field": "nonexistent_field"}
            }
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(bad_manifest, f)
            manifest_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                WorkflowEngine(
                    template_path="src/workflows/txt2img/workflow.json",
                    manifest_path=manifest_path,
                )
            assert "missing field" in str(exc_info.value).lower()
        finally:
            os.unlink(manifest_path)


class TestWorkflowEngineApply:
    """Unit tests for WorkflowEngine.apply_parameters."""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine(
            template_path="src/workflows/txt2img/workflow.json",
            manifest_path="src/workflows/txt2img/manifest.yaml",
        )

    def test_apply_prompt(self, engine):
        """GIVEN a prompt parameter
        WHEN applying parameters
        THEN the prompt node is updated.
        """
        resolved = engine.apply_parameters({"prompt": "a cyberpunk cat"})
        assert resolved["prompt"]["6"]["inputs"]["text"] == "a cyberpunk cat"

    def test_apply_negative_prompt(self, engine):
        """GIVEN a negative_prompt parameter
        WHEN applying parameters
        THEN the negative prompt node is updated.
        """
        resolved = engine.apply_parameters({"negative_prompt": "blurry, low quality"})
        assert resolved["prompt"]["7"]["inputs"]["text"] == "blurry, low quality"

    def test_apply_checkpoint(self, engine):
        """GIVEN a checkpoint parameter
        WHEN applying parameters
        THEN the checkpoint node is updated.
        """
        resolved = engine.apply_parameters({"checkpoint": "custom.safetensors"})
        assert resolved["prompt"]["4"]["inputs"]["ckpt_name"] == "custom.safetensors"

    def test_apply_multiple_params(self, engine):
        """GIVEN multiple parameters
        WHEN applying parameters
        THEN all corresponding nodes are updated.
        """
        resolved = engine.apply_parameters({
            "prompt": "a futuristic city",
            "negative_prompt": "text, watermark",
            "seed": 12345,
            "steps": 30,
            "width": 1024,
            "height": 1024,
        })
        assert resolved["prompt"]["6"]["inputs"]["text"] == "a futuristic city"
        assert resolved["prompt"]["7"]["inputs"]["text"] == "text, watermark"
        assert resolved["prompt"]["3"]["inputs"]["seed"] == 12345
        assert resolved["prompt"]["3"]["inputs"]["steps"] == 30
        assert resolved["prompt"]["5"]["inputs"]["width"] == 1024
        assert resolved["prompt"]["5"]["inputs"]["height"] == 1024

    def test_undeclared_param_rejected(self, engine):
        """GIVEN a parameter not in the manifest
        WHEN applying parameters
        THEN ValueError is raised.
        """
        with pytest.raises(ValueError) as exc_info:
            engine.apply_parameters({"undeclared_param": "value"})
        assert "not declared" in str(exc_info.value).lower()

    def test_original_template_unchanged(self, engine):
        """GIVEN apply_parameters is called
        WHEN inspecting the original template
        THEN it is not mutated.
        """
        original_prompt = engine.template["prompt"]["6"]["inputs"]["text"]
        engine.apply_parameters({"prompt": "mutated"})
        assert engine.template["prompt"]["6"]["inputs"]["text"] == original_prompt

    def test_empty_params_allowed(self, engine):
        """GIVEN empty params
        WHEN applying parameters
        THEN the template is returned unchanged.
        """
        resolved = engine.apply_parameters({})
        assert resolved == engine.template


class TestWorkflowEngineExecute:
    """Unit tests for WorkflowEngine.execute."""

    @pytest.fixture
    def engine(self):
        return WorkflowEngine(
            template_path="src/workflows/txt2img/workflow.json",
            manifest_path="src/workflows/txt2img/manifest.yaml",
        )

    def test_execute_returns_resolved_graph(self, engine):
        """GIVEN valid parameters
        WHEN execute is called
        THEN the resolved graph is returned.
        """
        result = engine.execute({"prompt": "test prompt"})
        assert result["prompt"]["6"]["inputs"]["text"] == "test prompt"


class TestProductPremiumWorkflowEngine:
    """Unit tests for the product premium workflow contract."""

    def test_loads_product_premium_manifest_and_format_metadata(self):
        """GIVEN the product premium workflow assets and whitelist
        WHEN creating a WorkflowEngine
        THEN the manifest loads with format metadata and resolution helpers.
        """
        whitelist = json.dumps({"checkpoints": ["juggernautXL_ragnarok.safetensors"], "loras": []})

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/product_premium/workflow.json",
                manifest_path="src/workflows/product_premium/manifest.yaml",
            )

        assert engine.manifest.default_checkpoint == "juggernautXL_ragnarok.safetensors"
        assert engine.manifest.default_format == "square"
        assert engine.manifest.formats["square"].width == 1024
        assert engine.manifest.formats["square"].height == 1024
        assert engine.manifest.formats["vertical"].width * 16 == engine.manifest.formats["vertical"].height * 9

        default_dimensions = engine.resolve_format_dimensions()
        vertical_dimensions = engine.resolve_format_dimensions("vertical")

        assert default_dimensions.width == 1024
        assert default_dimensions.height == 1024
        assert vertical_dimensions.width * 16 == vertical_dimensions.height * 9

    def test_rejects_non_whitelisted_product_checkpoint(self):
        """GIVEN a product manifest with a checkpoint outside the whitelist
        WHEN creating a WorkflowEngine
        THEN a validation error is raised.
        """
        whitelist = json.dumps({"checkpoints": ["v1-5-pruned-emaonly-fp16.safetensors"], "loras": []})

        bad_manifest = {
            "inputs": {
                "prompt": {"node_id": "6", "field": "text"},
                "checkpoint": {"node_id": "4", "field": "ckpt_name"},
                "width": {"node_id": "5", "field": "width"},
                "height": {"node_id": "5", "field": "height"},
            },
            "default_checkpoint": "epicrealism_naturalSinRC1VAE.safetensors",
            "default_format": "square",
            "formats": {
                "square": {"width": 1024, "height": 1024},
                "vertical": {"width": 720, "height": 1280},
            },
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(bad_manifest, f)
            manifest_path = f.name

        try:
            with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
                with pytest.raises(ValueError, match="model_not_allowed"):
                    WorkflowEngine(
                        template_path="src/workflows/txt2img/workflow.json",
                        manifest_path=manifest_path,
                    )
        finally:
            os.unlink(manifest_path)


class TestIdentidadGGUFWorkflowEngine:
    """Contract tests for the identidad_gguf workflow assets."""

    def test_loads_identity_gguf_manifest_and_declared_inputs(self):
        """GIVEN the identidad_gguf workflow assets and whitelist
        WHEN creating a WorkflowEngine
        THEN the manifest loads with all required runtime parameters and model inputs.
        """
        whitelist = json.dumps({
            "gguf": ["flux1-dev-q4_k_m.gguf"],
            "clip": ["t5xxl_fp8_e4m3fn.safetensors"],
            "pulid": ["pulid_flux_v0.9.1.safetensors"],
            "face_detector": ["face_yolov8m.onnx"],
        })

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            engine = WorkflowEngine(
                template_path="src/workflows/identidad_gguf/workflow.json",
                manifest_path="src/workflows/identidad_gguf/manifest.yaml",
            )

        assert set(["prompt", "image_url", "width", "height", "seed"]).issubset(engine.manifest.inputs)
        assert engine.manifest.defaults["width"] == 1024
        assert engine.manifest.defaults["height"] == 1024
        assert engine.manifest.defaults["seed"] == -1
        assert engine.template["prompt"]["6"]["class_type"] == "LoadImageFromBase64"
        assert "Screenshot" not in json.dumps(engine.template)

    def test_rejects_non_whitelisted_identity_gguf_manifest_model(self):
        """GIVEN the identidad_gguf manifest references a GGUF model outside the whitelist
        WHEN creating a WorkflowEngine
        THEN a model_not_allowed validation error is raised.
        """
        whitelist = json.dumps({
            "gguf": ["other.gguf"],
            "clip": ["t5xxl_fp8_e4m3fn.safetensors"],
            "pulid": ["pulid_flux_v0.9.1.safetensors"],
            "face_detector": ["face_yolov8m.onnx"],
        })

        with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": whitelist}, clear=False):
            with pytest.raises(ValueError, match="model_not_allowed") as exc_info:
                WorkflowEngine(
                    template_path="src/workflows/identidad_gguf/workflow.json",
                    manifest_path="src/workflows/identidad_gguf/manifest.yaml",
                )

        assert "flux1-dev-q4_k_m.gguf" in str(exc_info.value)


class TestWorkflowEngineManifestDefaults:
    """Unit tests for generic manifest defaults and prompt templates."""

    def test_apply_parameters_uses_manifest_defaults_before_runtime_prompt_templates(self):
        """GIVEN a manifest with defaults and a prompt template
        WHEN applying runtime parameters
        THEN defaults fill omitted controls and runtime values override defaults before rendering.
        """
        manifest = {
            "inputs": {
                "prompt": {"node_id": "6", "field": "text"},
                "negative_prompt": {"node_id": "7", "field": "text"},
                "age": {"node_id": "6", "field": "text"},
                "wardrobe": {"node_id": "6", "field": "text"},
                "output_type": {"node_id": "6", "field": "text"},
                "width": {"node_id": "5", "field": "width"},
                "height": {"node_id": "5", "field": "height"},
            },
            "defaults": {
                "age": 34,
                "wardrobe": "linen shirt",
                "output_type": "portrait",
                "negative_prompt": "waxy skin, plastic texture",
                "width": 768,
                "height": 1024,
            },
            "prompt-templates": {
                "prompt": (
                    "{output_type} of a {age}-year-old person wearing {wardrobe}. "
                    "{prompt}"
                )
            },
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(manifest, f)
            manifest_path = f.name

        try:
            engine = WorkflowEngine(
                template_path="src/workflows/txt2img/workflow.json",
                manifest_path=manifest_path,
            )

            resolved = engine.apply_parameters(
                {
                    "prompt": "documentary lighting",
                    "age": 52,
                }
            )
        finally:
            os.unlink(manifest_path)

        assert resolved["prompt"]["6"]["inputs"]["text"] == (
            "portrait of a 52-year-old person wearing linen shirt. documentary lighting"
        )
        assert resolved["prompt"]["7"]["inputs"]["text"] == "waxy skin, plastic texture"
        assert resolved["prompt"]["5"]["inputs"]["width"] == 768
        assert resolved["prompt"]["5"]["inputs"]["height"] == 1024

    def test_apply_parameters_rejects_prompt_template_with_missing_variable(self):
        """GIVEN a prompt template references an undeclared value
        WHEN applying parameters
        THEN the engine raises a validation error for the missing template variable.
        """
        manifest = {
            "inputs": {
                "prompt": {"node_id": "6", "field": "text"},
            },
            "prompt-templates": {
                "prompt": "{prompt} with {missing_control}",
            },
        }

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(manifest, f)
            manifest_path = f.name

        try:
            engine = WorkflowEngine(
                template_path="src/workflows/txt2img/workflow.json",
                manifest_path=manifest_path,
            )

            with pytest.raises(ValueError, match="missing_control"):
                engine.apply_parameters({"prompt": "documentary portrait"})
        finally:
            os.unlink(manifest_path)
