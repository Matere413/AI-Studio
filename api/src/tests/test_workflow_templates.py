"""Unit tests for workflow templates and manifests."""

import json
from pathlib import Path

import yaml
import pytest

from src.shared.workflows.models import ManifestSchema, NodeMapping


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
