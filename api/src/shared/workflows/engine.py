"""Workflow engine for loading ComfyUI templates and applying runtime parameters."""

import json
import os
from typing import Any, Dict, Optional

import yaml

from src.shared.workflows.cache import load_whitelist
from src.shared.workflows.models import FormatDimensions, ManifestSchema


class WorkflowEngine:
    """Load a ComfyUI JSON template and YAML manifest, then apply runtime parameters.

    Contract:
        - Load template and manifest on init.
        - Validate that manifest node IDs and fields exist in the template.
        - apply_parameters(params) returns a deep copy of the template with params injected.
        - execute(params) applies parameters and returns the resolved graph (ComfyUI API format).
    """

    def __init__(self, template_path: str, manifest_path: str):
        """Load and validate template + manifest.

        Args:
            template_path: Path to the ComfyUI JSON workflow template.
            manifest_path: Path to the YAML manifest mapping semantic inputs to nodes.

        Raises:
            FileNotFoundError: If either file is missing.
            ValueError: If the manifest references invalid nodes or fields.
            ValidationError: If the manifest YAML is malformed.
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(template_path, "r", encoding="utf-8") as f:
            self._template = json.load(f)

        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_manifest = yaml.safe_load(f)

        self._manifest = ManifestSchema.model_validate(raw_manifest)

        self._validate_references()
        self._validate_checkpoint_whitelist()

    def _validate_references(self) -> None:
        """Ensure every manifest node_id and field exists in the template.

        Raises:
            ValueError: If a reference is invalid.
        """
        nodes = self._template.get("prompt", {})
        for input_name, mapping in self._manifest.inputs.items():
            node_id = mapping.node_id
            field = mapping.field
            if node_id not in nodes:
                raise ValueError(
                    f"Manifest input '{input_name}' references missing node '{node_id}'"
                )
            node_inputs = nodes[node_id].get("inputs", {})
            if field not in node_inputs:
                raise ValueError(
                    f"Manifest input '{input_name}' references missing field "
                    f"'{field}' in node '{node_id}'"
                )

    def _validate_checkpoint_whitelist(self) -> None:
        """Ensure the manifest's default checkpoint is approved for loading."""
        default_checkpoint = self._manifest.default_checkpoint
        if not default_checkpoint:
            return

        whitelist = load_whitelist()
        allowed_checkpoints = whitelist.get("checkpoints", [])
        if default_checkpoint not in allowed_checkpoints:
            raise ValueError(
                f"model_not_allowed: Manifest checkpoint '{default_checkpoint}' is not in the approved whitelist"
            )

    def apply_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply runtime parameters to a deep copy of the template.

        Args:
            params: Dict of semantic input names to values (e.g., {"prompt": "a cat"}).

        Returns:
            A new dict representing the resolved ComfyUI workflow graph.

        Raises:
            ValueError: If a parameter is provided that is not declared in the manifest.
        """
        # Deep copy the template
        resolved = json.loads(json.dumps(self._template))
        nodes = resolved["prompt"]

        # Validate that all provided params are declared
        for key in params:
            if key not in self._manifest.inputs:
                raise ValueError(
                    f"Parameter '{key}' is not declared by the workflow manifest"
                )

        # Apply mappings
        for key, value in params.items():
            mapping = self._manifest.inputs[key]
            nodes[mapping.node_id]["inputs"][mapping.field] = value

        return resolved

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow by applying parameters and returning the resolved graph.

        In production this would dispatch to a ComfyUI client; for the engine layer
        it returns the resolved graph ready for execution.

        Args:
            params: Runtime parameters to inject.

        Returns:
            The resolved ComfyUI API-format workflow dict.
        """
        return self.apply_parameters(params)

    def resolve_format_dimensions(self, format_name: Optional[str] = None) -> FormatDimensions:
        """Resolve a declared format name to its workflow-owned dimensions."""
        if not self._manifest.formats:
            raise ValueError("Workflow manifest does not declare format dimensions")

        selected_format = format_name or self._manifest.default_format
        if not selected_format:
            raise ValueError("Workflow manifest does not declare a default format")

        try:
            return self._manifest.formats[selected_format]
        except KeyError as exc:
            raise ValueError(
                f"Format '{selected_format}' is not declared by the workflow manifest"
            ) from exc

    @property
    def manifest(self) -> ManifestSchema:
        """Access the loaded manifest schema."""
        return self._manifest

    @property
    def template(self) -> Dict[str, Any]:
        """Access the loaded template."""
        return self._template
