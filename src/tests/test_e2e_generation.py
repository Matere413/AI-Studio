import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app import fastapi_app
from src.features.generation.router import _job_store


@pytest.fixture(autouse=True)
def mock_run_generation():
    with patch("src.features.generation.modal_tasks.run_generation") as mock:
        mock.spawn.return_value = None
        yield mock


client = TestClient(fastapi_app)


class TestE2EGenerationFlow:
    """End-to-end tests covering the full POST + WebSocket lifecycle."""

    def test_e2e_accepted_request(self):
        """GIVEN a client sends a valid prompt
        WHEN POST /generate is called
        THEN 202 Accepted with job_id is returned
        AND the WebSocket streams a pending event.
        """
        response = client.post("/generate", json={"prompt": "e2e accepted"})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify WebSocket streams the pending event
        with client.websocket_connect(f"/ws/generate/{data['job_id']}") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "pending"
            assert event["job_id"] == data["job_id"]

    def test_e2e_validation_failure(self):
        """GIVEN a client sends an invalid payload
        WHEN POST /generate is called
        THEN the request is rejected with validation error.
        """
        # Missing prompt
        response = client.post("/generate", json={})
        assert response.status_code == 422

        # Empty prompt
        response = client.post("/generate", json={"prompt": ""})
        assert response.status_code == 422

        # Extra fields
        response = client.post("/generate", json={"prompt": "valid", "extra": "field"})
        assert response.status_code == 422

    def test_e2e_unknown_job(self):
        """GIVEN no job exists for a requested job_id
        WHEN WS /ws/generate/{job_id} is called
        THEN an error event with not-found code is returned.
        """
        with client.websocket_connect("/ws/generate/non-existent-e2e-job") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "error"
            assert event["error"]["code"] == "NOT_FOUND"

    def test_e2e_reconnect(self):
        """GIVEN a job is active and a client disconnects
        WHEN the client reconnects with the same job_id
        THEN the server resumes by sending the current known lifecycle state.
        """
        response = client.post("/generate", json={"prompt": "e2e reconnect"})
        job_id = response.json()["job_id"]

        # First connection
        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "pending"

        # Update job to running
        _job_store.update_job(job_id, status="running")

        # Reconnect
        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "running"
            assert event["progress"] == 50
            assert event["message"] == "Processing"

    def test_e2e_completed_stream(self):
        """GIVEN a generation job completes
        WHEN a client connects to WS
        THEN the completed event is streamed and connection closes.
        """
        response = client.post("/generate", json={"prompt": "e2e completed"})
        job_id = response.json()["job_id"]

        # Complete the job
        _job_store.update_job(job_id, status="completed", image_path="/e2e/image.png")

        with client.websocket_connect(f"/ws/generate/{job_id}") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "completed"
            assert event["result"]["image_path"] == "/e2e/image.png"

            # Connection closes after terminal event
            with pytest.raises(Exception):
                websocket.receive_json()

    def test_e2e_checkpoint_url_accepted(self):
        """GIVEN a client sends checkpoint_url
        WHEN POST /generate is called
        THEN 202 Accepted with job_id is returned.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "e2e checkpoint",
                "checkpoint_url": "https://example.com/model.safetensors",
                "workflow_name": "txt2img",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify WebSocket still works
        with client.websocket_connect(f"/ws/generate/{data['job_id']}") as websocket:
            event = websocket.receive_json()
            assert event["event"] == "pending"
            assert event["job_id"] == data["job_id"]

    def test_e2e_unsupported_param_rejected(self):
        """GIVEN a client sends an unsupported parameter for the workflow
        WHEN POST /generate is called
        THEN 422 Unprocessable Entity is returned.
        """
        response = client.post(
            "/generate",
            json={
                "prompt": "e2e unsupported",
                "lora_url": "https://example.com/lora.safetensors",
                "workflow_name": "txt2img",
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "lora" in detail.lower()

    def test_e2e_backward_compatible_prompt_only(self):
        """GIVEN a legacy prompt-only request
        WHEN POST /generate is called
        THEN 202 Accepted with job_id is returned.
        """
        response = client.post("/generate", json={"prompt": "legacy e2e"})
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
