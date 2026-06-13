import json
import os
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch
from src.features.generation.router import router as generation_router, _job_store


WHITELIST_JSON = json.dumps({
    "checkpoints": ["model.safetensors", "sdxl.safetensors", "sd15.safetensors"],
    "loras": ["lora.safetensors", "detail_enhancer.safetensors"],
})


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def mock_download_model():
    with patch("src.shared.workflows.cache.download_model") as mock:
        mock.spawn.return_value = None
        yield mock


@pytest.fixture(autouse=True)
def whitelist():
    with patch.dict(os.environ, {"ALLOWED_MODELS_JSON": WHITELIST_JSON}, clear=False):
        yield


# Create a minimal FastAPI app for testing the router
app = FastAPI()
app.include_router(generation_router)
client = TestClient(app)


class TestPostGenerate:
    """Integration tests for POST /generate endpoint."""

    def test_valid_request_returns_202(self):
        """GIVEN a valid non-empty prompt
        WHEN POST /generate is called
        THEN the response status is 202
        AND the body contains a unique job_id and status='pending'.
        """
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0
        assert data["status"] == "pending"

    def test_missing_prompt_returns_422(self):
        """GIVEN no prompt is provided
        WHEN POST /generate is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/generate", json={})
        assert response.status_code == 422

    def test_empty_prompt_returns_422(self):
        """GIVEN an empty prompt string
        WHEN POST /generate is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/generate", json={"prompt": ""})
        assert response.status_code == 422

    def test_prompt_too_long_returns_422(self):
        """GIVEN a prompt exceeding 4000 characters
        WHEN POST /generate is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/generate", json={"prompt": "x" * 4001})
        assert response.status_code == 422

    def test_extra_fields_rejected(self):
        """GIVEN extra fields are provided
        WHEN POST /generate is called
        THEN the request is rejected with a validation error.
        """
        response = client.post("/generate", json={"prompt": "valid", "extra": "field"})
        assert response.status_code == 422

    def test_checkpoint_url_accepted(self):
        """GIVEN a checkpoint_url is provided
        WHEN POST /generate is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "a cyberpunk cat",
                "checkpoint_url": "https://example.com/model.safetensors",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_model_not_allowed_returns_400(self):
        """GIVEN a non-whitelisted checkpoint_url
        WHEN POST /generate is called
        THEN the response is 400 with error.code = model_not_allowed.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "a cyberpunk cat",
                "checkpoint_url": "https://example.com/forbidden.safetensors",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "model_not_allowed"
        assert "forbidden.safetensors" in data["error"]["detail"]

    def test_lora_url_rejected_for_txt2img(self):
        """GIVEN a lora_url is provided for txt2img (which does not support lora)
        WHEN POST /generate is called
        THEN the request is rejected with 422.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "a cyberpunk cat",
                "lora_url": "https://example.com/lora.safetensors",
            },
        )
        assert response.status_code == 422
        assert "lora" in response.json()["detail"].lower()

    def test_workflow_name_accepted(self):
        """GIVEN a workflow_name is provided
        WHEN POST /generate is called
        THEN the request is accepted with 202.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "a cyberpunk cat",
                "workflow_name": "txt2img",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    def test_unsupported_param_rejected(self):
        """GIVEN an unsupported parameter for the selected workflow
        WHEN POST /generate is called
        THEN the request is rejected with 422.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "a cyberpunk cat",
                "checkpoint_url": "https://example.com/model.safetensors",
                "lora_url": "https://example.com/lora.safetensors",
                "workflow_name": "txt2img",
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "lora" in detail.lower()
        assert "not supported" in detail.lower()

    def test_backward_compatible_prompt_only(self):
        """GIVEN only a prompt (legacy request)
        WHEN POST /generate is called
        THEN the request is accepted with 202.
        """
        response = client.post("/generate", json={"prompt": "legacy prompt"})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"


class TestWebSocketGenerate:
    """Integration tests for WS /ws/generate/{job_id} endpoint."""

    def test_unknown_job_returns_error_event(self):
        """GIVEN no job exists for the requested job_id
        WHEN a client connects to WS /ws/generate/{job_id}
        THEN the server sends an error event with not-found code.
        """
        with client.websocket_connect("/ws/generate/non-existent-job") as websocket:
            data = websocket.receive_json()
            assert data["event"] == "error"
            assert data["job_id"] == "non-existent-job"
            assert "error" in data
            assert data["error"]["code"] == "NOT_FOUND"
            assert len(data["error"]["detail"]) > 0

    def test_known_job_returns_terminal_event(self):
        """GIVEN a valid job exists
        WHEN a client connects to WS /ws/generate/{job_id}
        THEN the server sends the current lifecycle event.
        """
        # First create a job
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()
            assert data["event"] in ["pending", "running", "completed", "error"]
            assert data["job_id"] == job_id
            assert "timestamp" in data

    def test_terminal_event_disconnects(self):
        """GIVEN a job reaches terminal state
        WHEN a client connects to WS /ws/generate/{job_id}
        THEN after the terminal event, the connection closes.
        """
        # Create a job that will be in completed state
        response = client.post("/generate", json={"prompt": "a cyberpunk cat"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()
            assert data["event"] in ["pending", "running", "completed", "error"]

            # After terminal event, connection should close
            if data["event"] in ["completed", "error"]:
                with pytest.raises(Exception):
                    websocket.receive_json()


class TestWebSocketPolling:
    """Integration tests for WebSocket polling and resume semantics."""

    def test_reconnect_resumes_current_state(self):
        """GIVEN a job is active and a client disconnects
        WHEN the client reconnects with the same job_id
        THEN the server resumes by sending the current known lifecycle state.
        """
        response = client.post("/generate", json={"prompt": "reconnect test"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # First connection: receive pending
        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()
            assert data["event"] == "pending"

        # Update job to running
        _job_store.update_job(job_id, status="running")

        # Reconnect: should receive running state
        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()
            assert data["event"] == "running"
            assert data["progress"] == 50
            assert data["message"] == "Processing"

    def test_reconnect_to_completed_job_closes(self):
        """GIVEN a job is completed
        WHEN a client reconnects
        THEN completed event is sent and connection closes.
        """
        response = client.post("/generate", json={"prompt": "completed reconnect test"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Complete the job
        _job_store.update_job(job_id, status="completed", image_path="/path/to/image.png")

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            data = websocket.receive_json()
            assert data["event"] == "completed"
            assert data["result"]["image_path"] == "/path/to/image.png"

            # Connection should close after terminal event
            with pytest.raises(Exception):
                websocket.receive_json()

    def test_polling_sends_state_changes(self):
        """GIVEN a job exists and state changes
        WHEN connected to WS
        THEN multiple events are sent as state changes.
        """
        import threading
        import time
        from unittest.mock import patch
        from src.features.generation import router as router_module

        response = client.post("/generate", json={"prompt": "polling test"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Update job state in background
        def update_states():
            time.sleep(0.05)
            _job_store.update_job(job_id, status="running")
            time.sleep(0.05)
            _job_store.update_job(job_id, status="completed", image_path="/path/to/image.png")

        thread = threading.Thread(target=update_states)
        thread.start()

        with patch.object(router_module, "POLL_INTERVAL", 0.01):
            with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
                # First event: pending
                data = websocket.receive_json()
                assert data["event"] == "pending"

                # Second event: running
                data = websocket.receive_json()
                assert data["event"] == "running"
                assert data["progress"] == 50
                assert data["message"] == "Processing"

                # Third event: completed
                data = websocket.receive_json()
                assert data["event"] == "completed"
                assert data["result"]["image_path"] == "/path/to/image.png"

        thread.join()
