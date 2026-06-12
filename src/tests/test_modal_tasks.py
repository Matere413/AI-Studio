import json
import os
import pytest
from src.features.generation.modal_tasks import mutate_comfy_payload


class TestMutateComfyPayload:
    """Unit tests for ComfyUI payload mutation."""

    def test_payload_mutates_positive_prompt(self):
        """GIVEN a custom prompt
        WHEN mutating the payload
        THEN the positive prompt node (6) contains the custom text.
        """
        payload = mutate_comfy_payload("a cyberpunk cat")
        assert payload["prompt"]["6"]["inputs"]["text"] == "a cyberpunk cat"

    def test_payload_preserves_other_nodes(self):
        """GIVEN a custom prompt
        WHEN mutating the payload
        THEN other nodes (negative prompt, sampler, etc.) are preserved.
        """
        payload = mutate_comfy_payload("a cyberpunk cat")
        # Negative prompt (node 7) should be preserved
        assert payload["prompt"]["7"]["inputs"]["text"] == "text, watermark"
        # Sampler (node 3) should be preserved
        assert payload["prompt"]["3"]["inputs"]["sampler_name"] == "euler"

    def test_payload_preserves_structure(self):
        """GIVEN a custom prompt
        WHEN mutating the payload
        THEN the overall structure is valid.
        """
        payload = mutate_comfy_payload("a cyberpunk cat")
        assert "prompt" in payload
        assert isinstance(payload["prompt"], dict)
        # Check all required nodes exist
        assert "3" in payload["prompt"]  # KSampler
        assert "4" in payload["prompt"]  # CheckpointLoader
        assert "5" in payload["prompt"]  # EmptyLatentImage
        assert "6" in payload["prompt"]  # CLIPTextEncode (positive)
        assert "7" in payload["prompt"]  # CLIPTextEncode (negative)
        assert "8" in payload["prompt"]  # VAEDecode
        assert "9" in payload["prompt"]  # SaveImage

    def test_different_prompts_produce_different_payloads(self):
        """GIVEN different prompts
        WHEN mutating the payload
        THEN each payload has the corresponding prompt text.
        """
        payload1 = mutate_comfy_payload("a cyberpunk cat")
        payload2 = mutate_comfy_payload("a futuristic city")
        assert payload1["prompt"]["6"]["inputs"]["text"] == "a cyberpunk cat"
        assert payload2["prompt"]["6"]["inputs"]["text"] == "a futuristic city"
        # Negative prompt should be the same in both
        assert payload1["prompt"]["7"]["inputs"]["text"] == payload2["prompt"]["7"]["inputs"]["text"]

    def test_empty_prompt(self):
        """GIVEN an empty prompt
        WHEN mutating the payload
        THEN the positive prompt node contains the empty string.
        """
        payload = mutate_comfy_payload("")
        assert payload["prompt"]["6"]["inputs"]["text"] == ""

    def test_payload_file_exists(self):
        """GIVEN the payload.json file
        WHEN loading it
        THEN the file is accessible and valid JSON.
        """
        # payload.json is co-located with modal_tasks.py under src/features/generation/
        payload_path = os.path.join(os.path.dirname(__file__), "..", "features", "generation", "payload.json")
        abs_path = os.path.abspath(payload_path)
        assert os.path.exists(abs_path)
        with open(abs_path, "r") as f:
            data = json.load(f)
        assert "prompt" in data
