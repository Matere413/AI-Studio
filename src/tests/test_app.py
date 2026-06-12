import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_app_is_fastapi_instance():
    """GIVEN app.py is imported
    THEN fastapi_app is a FastAPI instance.
    """
    from app import fastapi_app
    assert isinstance(fastapi_app, FastAPI)


def test_app_includes_generation_router():
    """GIVEN the mounted FastAPI app
    WHEN POST /generate is called
    THEN it returns 202 Accepted with a job_id.
    """
    from app import fastapi_app
    client = TestClient(fastapi_app)
    response = client.post("/generate", json={"prompt": "test app"})
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"


def test_app_websocket_unknown_job():
    """GIVEN the mounted FastAPI app
    WHEN WS /ws/generate/{unknown_job_id} is called
    THEN it returns an error event.
    """
    from app import fastapi_app
    client = TestClient(fastapi_app)
    with client.websocket_connect("/ws/generate/unknown-job") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "error"
        assert data["error"]["code"] == "NOT_FOUND"
