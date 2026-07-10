import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient

from src.shared.errors import register_app_error_handlers
from src.shared.rate_limit import RATE_LIMITER
from src.shared.telemetry import ALLOWED_FRONTEND_EVENT_NAMES, EVENT_ID_BOOTSTRAP_TRANSIENT
from src.shared import telemetry_router
from src.shared.telemetry_router import router
@pytest.fixture
def client():
    app = FastAPI()
    register_app_error_handlers(app)
    app.include_router(router)
    return TestClient(app)
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    RATE_LIMITER.reset()
def post(client, payload, **kwargs):
    return client.post("/telemetry/events", json=payload, **kwargs)
def test_accepts_anonymous_allowlisted_primitives_and_default_level(client, monkeypatch):
    captured = []
    monkeypatch.setattr("src.shared.telemetry_router.capture_frontend_event", lambda **event: captured.append(event))
    response = post(client, {"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"code": "timeout", "attempts": 3, "recovered": False, "detail": None}})
    assert response.status_code == 202 and response.json() == {"accepted": True}
    assert captured == [{"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"code": "timeout", "attempts": 3, "recovered": False, "detail": None}, "level": "info"}]
    assert EVENT_ID_BOOTSTRAP_TRANSIENT in ALLOWED_FRONTEND_EVENT_NAMES
@pytest.mark.parametrize("payload,code", [
    ({"name": "invented_event", "fields": {}}, "unknown_event"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {}, "token": "x"}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"nested": {"x": 1}}}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"items": [1]}}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {}, "level": "critical"}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"x" * 65: "ok"}}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {"code": "x" * 513}}, "invalid_body"),
    ({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {f"key_{i}": i for i in range(33)}}, "invalid_body"),
    *[({"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {name: "x"}}, "invalid_body") for name in ("accessToken", "COOKIE", "api_key", "Authorization", "userEmail", "request_body")],
])
def test_rejects_unallowlisted_or_invalid_payloads(client, payload, code):
    response = post(client, payload)
    assert response.status_code == 422 and response.json()["error"]["code"] == code
def test_limits_body_and_requests_including_rotating_untrusted_xff(client, monkeypatch):
    captured = []
    monkeypatch.setattr("src.shared.telemetry_router.capture_frontend_event", lambda **event: captured.append(event))
    oversized = client.post("/telemetry/events", content=b'{"name":"auth_bootstrap_transient","fields":{"detail":"' + b"x" * (16 * 1024) + b'"}}', headers={"content-type": "application/json"})
    assert oversized.status_code == 413 and not captured
    RATE_LIMITER.reset()
    for i in range(30):
        assert post(client, {"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {}}, headers={"x-forwarded-for": f"203.0.113.{i}"}).status_code == 202
    assert post(client, {"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {}}, headers={"x-forwarded-for": "198.51.100.99"}).status_code == 429
    assert len(captured) == 30
@pytest.mark.parametrize("enabled,allowlist,peer,xff,expected", [
    (True, {"10.0.0.1"}, "10.0.0.1", "203.0.113.7, 10.0.0.1", "203.0.113.7"),
    (True, {"10.0.0.1"}, "198.51.100.1", "203.0.113.7", "198.51.100.1"),
    (False, {"10.0.0.1"}, "10.0.0.1", "203.0.113.7", "10.0.0.1"),
    (True, {"10.0.0.1"}, "10.0.0.1", "rotated-xff", "10.0.0.1"),
])
def test_client_ip_trusts_only_valid_xff_from_allowlisted_proxy(monkeypatch, enabled, allowlist, peer, xff, expected):
    monkeypatch.setattr(telemetry_router, "_TRUSTED_PROXY", enabled)
    monkeypatch.setattr(telemetry_router, "_TRUSTED_PROXY_IPS", allowlist)
    request = Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())], "client": (peer, 1)})
    assert telemetry_router._client_ip(request) == expected
def test_capture_failure_is_accepted(client, monkeypatch):
    monkeypatch.setattr("src.shared.telemetry_router.capture_frontend_event", lambda **_: (_ for _ in ()).throw(RuntimeError()))
    assert post(client, {"name": EVENT_ID_BOOTSTRAP_TRANSIENT, "fields": {}}).status_code == 202
