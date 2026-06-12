import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.features.generation.router import router as generation_router


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
