"""Behavior-first delivery executor and direct Resend transport tests."""

from __future__ import annotations

import threading

import httpx
import pytest

from src.features.auth.infrastructure.email_client import (
    BoundedDeliveryPool, ResendEmailClient, _reset_pool_for_tests, shutdown_delivery_pool,
)
from src.features.auth.infrastructure.resend_transport import (
    ResendHttpError, ResendSendRequest, derive_idempotency_key, resend_send,
)


@pytest.fixture(autouse=True)
def fresh_pool():
    _reset_pool_for_tests()
    yield
    _reset_pool_for_tests()


def test_pool_shutdown_rejects_new_work_and_cancels_queued_work():
    pool = BoundedDeliveryPool(max_workers=1, max_queued=1, submit_timeout_ms=0)
    running = threading.Event()
    release = threading.Event()

    def block():
        running.set()
        release.wait(timeout=2)

    active = pool.submit(block)
    assert active is not None and running.wait(timeout=1)
    queued = pool.submit(lambda: None)
    assert queued is not None
    pool.shutdown()
    assert pool.submit(lambda: None) is None
    assert queued.cancelled()
    release.set()


def test_pool_rejects_at_exact_running_and_queued_capacity():
    pool = BoundedDeliveryPool(max_workers=1, max_queued=1, submit_timeout_ms=0)
    running = threading.Event()
    release = threading.Event()

    def block():
        running.set()
        release.wait(timeout=2)

    active = pool.submit(block)
    assert active is not None and running.wait(timeout=1)
    queued = pool.submit(lambda: None)
    assert queued is not None
    assert pool.submit(lambda: None) is None
    release.set()
    active.result(timeout=1)
    queued.result(timeout=1)
    pool.shutdown()


def test_application_shutdown_is_idempotent():
    shutdown_delivery_pool()
    shutdown_delivery_pool()


@pytest.mark.parametrize("status", [201, 204])
def test_direct_transport_accepts_every_2xx(status: int):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"id": "sent"}))
    result = resend_send(ResendSendRequest(api_key="re_test", from_email="noreply@test.io", to_email="u@test.io",
                         verification_url="https://app.test/auth/verify?token=secret",
                         idempotency_key="delivery-1"), transport=transport)
    assert result == {"id": "sent"}


def test_direct_transport_rejects_and_maps_non_2xx_response():
    transport = httpx.MockTransport(lambda request: httpx.Response(503, json={"message": "unavailable"}))
    with pytest.raises(ResendHttpError) as raised:
        resend_send(ResendSendRequest(api_key="re_test", from_email="noreply@test.io", to_email="u@test.io",
                    verification_url="https://app.test/auth/verify?token=secret",
                    idempotency_key="delivery-1"), transport=transport)
    assert raised.value.kind == "http_error"
    assert raised.value.status == 503


def test_client_uses_injected_transport_without_runtime_endpoint_override(monkeypatch):
    monkeypatch.delenv("RESEND_API_BASE_URL", raising=False)
    received = {}

    def handle(request: httpx.Request) -> httpx.Response:
        received["host"] = request.url.host
        received["authorization"] = request.headers["Authorization"]
        received["idempotency_key"] = request.headers["Idempotency-Key"]
        return httpx.Response(201, json={"id": "sent"})

    client = ResendEmailClient(api_key="re_test", from_email="noreply@test.io",
                               app_base_url="https://app.test", http_transport=httpx.MockTransport(handle))
    delivery_id = "delivery-1"
    assert client.send_verification(email="u@test.io", raw_token="raw-secret", delivery_id=delivery_id).success
    assert received == {"host": "api.resend.com", "authorization": "Bearer re_test",
                        "idempotency_key": derive_idempotency_key(delivery_id)}
