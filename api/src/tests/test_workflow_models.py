"""Unit tests for workflow manifest models."""

import pytest
from pydantic import ValidationError

from src.shared.workflows.models import FormatDimensions, ManifestSchema, NodeMapping


class TestNodeMapping:
    """Unit tests for NodeMapping Pydantic model."""

    def test_valid_node_mapping(self):
        """GIVEN a valid node_id and field
        WHEN creating a NodeMapping
        THEN the model validates successfully.
        """
        mapping = NodeMapping(node_id="3", field="text")
        assert mapping.node_id == "3"
        assert mapping.field == "text"

    def test_missing_node_id_rejected(self):
        """GIVEN no node_id is provided
        WHEN creating a NodeMapping
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            NodeMapping(field="text")

    def test_missing_field_rejected(self):
        """GIVEN no field is provided
        WHEN creating a NodeMapping
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            NodeMapping(node_id="3")

    def test_empty_node_id_rejected(self):
        """GIVEN an empty node_id
        WHEN creating a NodeMapping
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            NodeMapping(node_id="", field="text")

    def test_empty_field_rejected(self):
        """GIVEN an empty field
        WHEN creating a NodeMapping
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            NodeMapping(node_id="3", field="")


class TestManifestSchema:
    """Unit tests for ManifestSchema Pydantic model."""

    def test_valid_manifest(self):
        """GIVEN a valid manifest with inputs
        WHEN creating a ManifestSchema
        THEN the model validates successfully.
        """
        manifest = ManifestSchema(
            inputs={
                "prompt": NodeMapping(node_id="3", field="text"),
                "checkpoint": NodeMapping(node_id="4", field="ckpt_name"),
            }
        )
        assert manifest.inputs["prompt"].node_id == "3"
        assert manifest.inputs["prompt"].field == "text"
        assert manifest.inputs["checkpoint"].node_id == "4"
        assert manifest.inputs["checkpoint"].field == "ckpt_name"

    def test_empty_inputs_allowed(self):
        """GIVEN an empty inputs dict
        WHEN creating a ManifestSchema
        THEN the model validates successfully.
        """
        manifest = ManifestSchema(inputs={})
        assert manifest.inputs == {}

    def test_missing_inputs_rejected(self):
        """GIVEN no inputs dict
        WHEN creating a ManifestSchema
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            ManifestSchema()

    def test_extra_fields_forbidden(self):
        """GIVEN extra fields are provided
        WHEN creating a ManifestSchema
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            ManifestSchema(
                inputs={"prompt": NodeMapping(node_id="3", field="text")},
                extra="field",
            )


class TestProductManifestSchema:
    """Unit tests for product premium manifest metadata."""

    def test_valid_product_manifest_metadata(self):
        """GIVEN product premium format metadata
        WHEN creating a ManifestSchema
        THEN the model validates successfully.
        """
        manifest = ManifestSchema(
            inputs={
                "prompt": NodeMapping(node_id="6", field="text"),
                "checkpoint": NodeMapping(node_id="4", field="ckpt_name"),
                "width": NodeMapping(node_id="5", field="width"),
                "height": NodeMapping(node_id="5", field="height"),
            },
            default_checkpoint="juggernautXL_ragnarok.safetensors",
            default_format="square",
            formats={
                "square": FormatDimensions(width=1024, height=1024),
                "vertical": FormatDimensions(width=720, height=1280),
            },
        )

        assert manifest.default_checkpoint == "juggernautXL_ragnarok.safetensors"
        assert manifest.default_format == "square"
        assert manifest.formats["square"].width == 1024
        assert manifest.formats["square"].height == 1024
        assert manifest.formats["vertical"].width * 16 == manifest.formats["vertical"].height * 9

    def test_default_format_must_be_supported(self):
        """GIVEN a default format that is not declared
        WHEN creating a ManifestSchema
        THEN a ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            ManifestSchema(
                inputs={
                    "prompt": NodeMapping(node_id="6", field="text"),
                    "checkpoint": NodeMapping(node_id="4", field="ckpt_name"),
                },
                default_checkpoint="epicrealism_naturalSinRC1VAE.safetensors",
                default_format="panoramic",
                formats={
                    "square": FormatDimensions(width=1024, height=1024),
                    "vertical": FormatDimensions(width=720, height=1280),
                },
            )


class TestPersonaManifestSchema:
    """Unit tests for persona workflow manifest metadata."""

    def test_valid_manifest_supports_defaults_prompt_templates_and_persona_metadata(self):
        """GIVEN a persona manifest with default values and template metadata
        WHEN creating a ManifestSchema
        THEN defaults, prompt templates, and persona metadata validate successfully.
        """
        manifest = ManifestSchema.model_validate(
            {
                "inputs": {
                    "prompt": {"node_id": "6", "field": "text"},
                    "negative_prompt": {"node_id": "7", "field": "text"},
                    "age": {"node_id": "6", "field": "text"},
                    "gender": {"node_id": "6", "field": "text"},
                    "output_type": {"node_id": "6", "field": "text"},
                },
                "defaults": {
                    "age": 34,
                    "gender": "person",
                    "ethnicity": "unspecified",
                    "wardrobe": "timeless casual wardrobe",
                    "expression": "relaxed, natural expression",
                    "background": "soft environmental background",
                    "output_type": "portrait",
                },
                "prompt-templates": {
                    "prompt": (
                        "{output_type} of a {age}-year-old {ethnicity} {gender}, "
                        "{wardrobe}, {expression}, {background}. {prompt}"
                    ),
                    "negative_prompt": "{negative_prompt}",
                },
                "persona-metadata": {
                    "controls": [
                        "age",
                        "gender",
                        "ethnicity",
                        "wardrobe",
                        "expression",
                        "background",
                    ],
                    "output_types": ["portrait", "full-body", "lifestyle", "editorial"],
                },
            }
        )

        assert manifest.defaults["age"] == 34
        assert manifest.prompt_templates["prompt"].startswith("{output_type}")
        assert manifest.persona_metadata["controls"] == [
            "age",
            "gender",
            "ethnicity",
            "wardrobe",
            "expression",
            "background",
        ]
        assert manifest.persona_metadata["output_types"] == [
            "portrait",
            "full-body",
            "lifestyle",
            "editorial",
        ]

    def test_manifest_metadata_defaults_remain_empty_for_legacy_workflows(self):
        """GIVEN a legacy manifest without persona metadata
        WHEN creating a ManifestSchema
        THEN the new metadata fields default to empty dictionaries.
        """
        manifest = ManifestSchema(
            inputs={
                "prompt": NodeMapping(node_id="6", field="text"),
                "checkpoint": NodeMapping(node_id="4", field="ckpt_name"),
            }
        )

        assert manifest.defaults == {}
        assert manifest.prompt_templates == {}
        assert manifest.persona_metadata == {}


class TestWorkflowRequest:
    """Unit tests for WorkflowRequest base schema."""

    def test_valid_request_with_prompt_only(self):
        """GIVEN only a prompt
        WHEN creating a WorkflowRequest
        THEN the model validates successfully.
        """
        from src.shared.workflows.models import WorkflowRequest

        request = WorkflowRequest(prompt="a cyberpunk cat")
        assert request.prompt == "a cyberpunk cat"
        assert request.checkpoint_url is None
        assert request.lora_url is None

    def test_valid_request_with_all_fields(self):
        """GIVEN a prompt with checkpoint and lora URLs
        WHEN creating a WorkflowRequest
        THEN the model validates successfully.
        """
        from src.shared.workflows.models import WorkflowRequest

        request = WorkflowRequest(
            prompt="a cyberpunk cat",
            checkpoint_url="https://example.com/model.safetensors",
            lora_url="https://example.com/lora.safetensors",
        )
        assert request.checkpoint_url == "https://example.com/model.safetensors"
        assert request.lora_url == "https://example.com/lora.safetensors"

    def test_missing_prompt_rejected(self):
        """GIVEN no prompt
        WHEN creating a WorkflowRequest
        THEN a ValidationError is raised.
        """
        from src.shared.workflows.models import WorkflowRequest

        with pytest.raises(ValidationError):
            WorkflowRequest()

    def test_empty_prompt_rejected(self):
        """GIVEN an empty prompt
        WHEN creating a WorkflowRequest
        THEN a ValidationError is raised.
        """
        from src.shared.workflows.models import WorkflowRequest

        with pytest.raises(ValidationError):
            WorkflowRequest(prompt="")

    def test_extra_fields_forbidden(self):
        """GIVEN extra fields not declared by the workflow
        WHEN creating a WorkflowRequest
        THEN a ValidationError is raised.
        """
        from src.shared.workflows.models import WorkflowRequest

        with pytest.raises(ValidationError):
            WorkflowRequest(prompt="valid prompt", extra="field")
