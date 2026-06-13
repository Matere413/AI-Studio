import json
import pytest
import time
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


def _http_response_mock(body: bytes) -> MagicMock:
    """Build a MagicMock that works as a context-manager HTTP response."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestComfyUIClientProgress:
    """Unit tests for ComfyUI progress tracking and execution helpers."""

    def test_wait_ready_returns_when_server_responds(self):
        """GIVEN ComfyUI responds to system_stats
        WHEN wait_ready is called
        THEN it returns without raising.
        """
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.wait_ready(timeout_s=1.0)
            mock_urlopen.assert_called()

    def test_wait_ready_raises_timeout_when_server_unavailable(self):
        """GIVEN ComfyUI never responds
        WHEN wait_ready is called with a short timeout
        THEN it raises TimeoutError.
        """
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            with patch("src.shared.comfy_client.time.sleep"):
                client = ComfyUIClient(server_address="127.0.0.1:8188")
                with pytest.raises(TimeoutError):
                    client.wait_ready(timeout_s=0.1)

    def test_queue_prompt_returns_prompt_id(self):
        """GIVEN a payload
        WHEN queue_prompt is called
        THEN it returns the prompt_id from the response.
        """
        response = {"prompt_id": "abc-123", "number": 1, "node_errors": {}}
        mock_resp = _http_response_mock(json.dumps(response).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.client_id = "test-id"
            payload = {"prompt": {"6": {"inputs": {"text": "test"}}}}
            prompt_id = client.queue_prompt(payload)
            assert prompt_id == "abc-123"

    def test_queue_prompt_raises_on_http_error(self):
        """GIVEN the server returns an error
        WHEN queue_prompt is called
        THEN it raises an exception.
        """
        from urllib.error import HTTPError

        with patch(
            "urllib.request.urlopen",
            side_effect=HTTPError(url="http://127.0.0.1:8188/prompt", code=500, msg="Internal Error", hdrs={}, fp=None),
        ):
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            with pytest.raises(HTTPError):
                client.queue_prompt({"prompt": {}})

    def test_stream_progress_yields_progress_events(self):
        """GIVEN a progress WebSocket message
        WHEN stream_progress consumes it
        THEN it yields a progress event with the computed percent.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "progress", "data": {"value": 5, "max": 10, "prompt_id": "p1"}}),
            json.dumps({"type": "executed", "data": {"prompt_id": "p1"}}),
        ]

        events = list(client.stream_progress("p1", deadline=time.monotonic() + 5.0))

        assert len(events) == 1
        assert events[0]["event"] == "progress"
        assert events[0]["progress"] == 50

    def test_stream_progress_yields_generating_on_executing(self):
        """GIVEN an executing message
        WHEN stream_progress consumes it
        THEN it yields a generating event.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "executing", "data": {"node": "7", "prompt_id": "p1"}}),
            json.dumps({"type": "executed", "data": {"prompt_id": "p1"}}),
        ]

        events = list(client.stream_progress("p1", deadline=time.monotonic() + 5.0))

        assert events[0]["event"] == "generating"
        assert events[0]["progress"] == 0
        assert "node 7" in events[0]["message"]

    def test_stream_progress_yields_error_on_execution_error(self):
        """GIVEN an execution_error message
        WHEN stream_progress consumes it
        THEN it yields an error event and stops.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "execution_error", "data": {"prompt_id": "p1", "error": "node failed"}}),
        ]

        events = list(client.stream_progress("p1", deadline=time.monotonic() + 5.0))

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert "node failed" in events[0]["message"]

    def test_stream_progress_ignores_other_prompt_ids(self):
        """GIVEN messages for a different prompt_id
        WHEN stream_progress consumes events
        THEN it ignores them and waits for the target prompt.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "progress", "data": {"value": 1, "max": 2, "prompt_id": "other"}}),
            json.dumps({"type": "executed", "data": {"prompt_id": "p1"}}),
        ]

        events = list(client.stream_progress("p1", deadline=time.monotonic() + 5.0))

        assert len(events) == 0

    def test_stream_progress_raises_timeout_on_deadline(self):
        """GIVEN the deadline expires before completion
        WHEN stream_progress is called
        THEN it raises TimeoutError.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "progress", "data": {"value": 1, "max": 10, "prompt_id": "p1"}}),
            json.dumps({"type": "progress", "data": {"value": 2, "max": 10, "prompt_id": "p1"}}),
        ]

        with pytest.raises(TimeoutError):
            list(client.stream_progress("p1", deadline=time.monotonic() - 0.1))

    def test_resolve_output_path_returns_first_image(self):
        """GIVEN a history response with images
        WHEN resolve_output_path is called
        THEN it returns the full path to the first image.
        """
        history = {
            "outputs": {
                "9": {
                    "images": [{"filename": "img.png", "subfolder": "", "type": "output"}]
                }
            }
        }
        mock_resp = _http_response_mock(json.dumps(history).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            path = client.resolve_output_path("p1", "/root/ComfyUI/output")
            assert path == "/root/ComfyUI/output/img.png"

    def test_resolve_output_path_uses_subfolder(self):
        """GIVEN a history response with a subfolder
        WHEN resolve_output_path is called
        THEN the subfolder is included in the returned path.
        """
        history = {
            "outputs": {
                "9": {
                    "images": [{"filename": "img.png", "subfolder": "2024-01", "type": "output"}]
                }
            }
        }
        mock_resp = _http_response_mock(json.dumps(history).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            path = client.resolve_output_path("p1", "/root/ComfyUI/output")
            assert path == "/root/ComfyUI/output/2024-01/img.png"

    def test_resolve_output_path_raises_when_no_outputs(self):
        """GIVEN a history response with no images
        WHEN resolve_output_path is called
        THEN it raises RuntimeError.
        """
        mock_resp = _http_response_mock(json.dumps({"outputs": {}}).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp):
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            with pytest.raises(RuntimeError):
                client.resolve_output_path("p1", "/root/ComfyUI/output")


class TestComfyUIClientTimeouts:
    """Unit tests proving blocking HTTP/WS calls respect deadlines."""

    def test_queue_prompt_passes_timeout_to_urlopen(self):
        """GIVEN a timeout budget
        WHEN queue_prompt is called
        THEN the timeout is passed to urllib.request.urlopen.
        """
        response = {"prompt_id": "abc-123", "number": 1, "node_errors": {}}
        mock_resp = _http_response_mock(json.dumps(response).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.client_id = "test-id"
            client.queue_prompt({"prompt": {}}, timeout_s=42.0)
            _, kwargs = mock_urlopen.call_args
            assert kwargs.get("timeout") == 42.0

    def test_resolve_output_path_passes_timeout_to_urlopen(self):
        """GIVEN a timeout budget
        WHEN resolve_output_path is called
        THEN the timeout is passed to urllib.request.urlopen.
        """
        history = {
            "outputs": {
                "9": {
                    "images": [{"filename": "img.png", "subfolder": "", "type": "output"}]
                }
            }
        }
        mock_resp = _http_response_mock(json.dumps(history).encode("utf-8"))
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            client = ComfyUIClient(server_address="127.0.0.1:8188")
            client.resolve_output_path("p1", "/root/ComfyUI/output", timeout_s=77.0)
            _, kwargs = mock_urlopen.call_args
            assert kwargs.get("timeout") == 77.0

    def test_stream_progress_sets_websocket_timeout_before_recv(self):
        """GIVEN a deadline
        WHEN stream_progress receives messages
        THEN it sets the websocket timeout based on the remaining time before each recv.
        """
        client = ComfyUIClient()
        client.ws = MagicMock()
        client.ws.recv.side_effect = [
            json.dumps({"type": "executed", "data": {"prompt_id": "p1"}}),
        ]

        deadline = time.monotonic() + 123.0
        list(client.stream_progress("p1", deadline=deadline))

        assert client.ws.settimeout.called
        # The timeout passed should be close to the remaining budget (<= 123s)
        timeout_value = client.ws.settimeout.call_args[0][0]
        assert 0 < timeout_value <= 123.0
