"""Unit tests for the WorkflowEngine."""

import json
import os
from pathlib import Path

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
