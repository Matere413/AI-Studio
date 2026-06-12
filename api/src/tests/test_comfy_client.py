import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from src.shared.comfy_client import ComfyUIClient


class TestComfyUIClient:
    """Unit tests for ComfyUIClient extracted from legacy api.py."""

    def test_init_generates_client_id(self):
        """GIVEN a ComfyUIClient is created
        THEN it has a unique client_id.
        """
        client = ComfyUIClient()
        assert len(client.client_id) > 0

    def test_connect_creates_websocket(self):
        """GIVEN a ComfyUIClient
        WHEN connect is called
        THEN it creates a WebSocket connection.
        """
        with patch("src.shared.comfy_client.websocket.WebSocket") as MockWS:
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.connect()
            MockWS.assert_called_once()
            MockWS.return_value.connect.assert_called_once_with(
                f"ws://127.0.0.1:8188/ws?clientId={client.client_id}"
            )

    def test_load_payload_reads_file(self):
        """GIVEN a payload file exists
        WHEN load_payload is called
        THEN it returns the parsed JSON.
        """
        mock_payload = {"prompt": {"6": {"inputs": {"text": "test"}}}}
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_payload))):
            client = ComfyUIClient()
            payload = client.load_payload("payload.json")
            assert payload == mock_payload

    def test_mutate_prompt_updates_text(self):
        """GIVEN a payload with a prompt node
        WHEN mutate_prompt is called
        THEN the text is updated.
        """
        client = ComfyUIClient()
        payload = {"prompt": {"6": {"inputs": {"text": "old"}}}}
        result = client.mutate_prompt(payload, "new")
        assert result["prompt"]["6"]["inputs"]["text"] == "new"

    def test_mutate_prompt_preserves_structure(self):
        """GIVEN a payload with multiple nodes
        WHEN mutate_prompt is called
        THEN only the text node is updated.
        """
        client = ComfyUIClient()
        payload = {"prompt": {"6": {"inputs": {"text": "old"}}, "7": {"inputs": {"seed": 42}}}}
        result = client.mutate_prompt(payload, "new")
        assert result["prompt"]["7"]["inputs"]["seed"] == 42

    def test_send_prompt_makes_request(self):
        """GIVEN a payload
        WHEN send_prompt is called
        THEN it makes an HTTP request to the ComfyUI server.
        """
        with patch("urllib.request.urlopen") as mock_urlopen:
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.client_id = "test-id"
            payload = {"prompt": {"6": {"inputs": {"text": "test"}}}}
            client.send_prompt(payload)
            mock_urlopen.assert_called_once()

    def test_listen_for_completion_returns_output(self):
        """GIVEN the WebSocket receives an executed message
        WHEN listen_for_completion is called
        THEN it returns the output data.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "other", "data": {}}),
            json.dumps({"type": "executed", "data": {"output": "image.png"}}),
        ]
        result = client.listen_for_completion()
        assert result == "image.png"

    def test_close_closes_websocket(self):
        """GIVEN a connected client
        WHEN close is called
        THEN the WebSocket is closed.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.close()
        client.ws.close.assert_called_once()
