"""Resend client composition over protocol, executor, and transport."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from functools import partial

import httpx

from src.features.auth.infrastructure.email_execution import (
    _decrement_in_flight, _increment_in_flight, get_delivery_pool, observe_late_resolution,
)
from src.features.auth.infrastructure.email_protocol import SendResult, TOKEN_PREFIX_LENGTH, build_verification_url
from src.features.auth.infrastructure.resend_transport import (
    ResendSendRequest, classify_send_failure, derive_idempotency_key, resend_send, resend_timeout_ms,
)
from src.shared.telemetry import capture_delivery_backpressure, capture_delivery_failed, capture_delivery_timeout


class ResendEmailClient:
    def __init__(self, *, api_key: str, from_email: str, app_base_url: str = "",
                 send_transport: Callable[[ResendSendRequest], dict] | None = None,
                 http_transport: httpx.BaseTransport | None = None) -> None:
        self._api_key, self._from_email, self._app_base_url = api_key, from_email, app_base_url
        self._send_transport = send_transport or partial(resend_send, transport=http_transport)

    def build_verification_url(self, *, email: str, raw_token: str) -> str:
        return build_verification_url(self._app_base_url, email, raw_token)

    def send_verification(self, *, email: str, raw_token: str, delivery_id: str | None = None) -> SendResult:
        timeout_ms, token_prefix = resend_timeout_ms(), raw_token[:TOKEN_PREFIX_LENGTH]
        _increment_in_flight()
        try:
            request = ResendSendRequest(
                api_key=self._api_key,
                from_email=self._from_email,
                to_email=email,
                verification_url=self.build_verification_url(email=email, raw_token=raw_token),
                idempotency_key=derive_idempotency_key(delivery_id),
            )
            future = get_delivery_pool().submit(self._send_on_thread, request)
            if future is None:
                capture_delivery_backpressure(provider="resend", timeout_ms=timeout_ms, token_prefix=token_prefix, reason="pool_unavailable")
                return SendResult(success=False)
            try:
                result = future.result(timeout=timeout_ms / 1000)
            except concurrent.futures.TimeoutError:
                if future.cancel():
                    capture_delivery_timeout(provider="resend", timeout_ms=timeout_ms, token_prefix=token_prefix, phase="queued")
                    return SendResult(success=False)
                capture_delivery_timeout(provider="resend", timeout_ms=timeout_ms, token_prefix=token_prefix, phase="running")
                future.add_done_callback(lambda completed: observe_late_resolution(completed, token_prefix))
                return SendResult(success=False, definitive=False)
            if "exc" in result:
                capture_delivery_failed(provider="resend", failure_category=classify_send_failure(result["exc"]), timeout_ms=timeout_ms, token_prefix=token_prefix)
                return SendResult(success=False)
            return SendResult(success=True)
        finally:
            _decrement_in_flight()

    def _send_on_thread(self, request: ResendSendRequest) -> dict:
        try:
            self._send_transport(request)
            return {"ok": True}
        except BaseException as exc:
            return {"exc": exc}


def build_email_client(*, provider: str, api_key: str | None = None, from_email: str = "", app_base_url: str = ""):
    from src.features.auth.infrastructure.email_protocol import DevEmailClient
    if provider == "resend" and api_key and from_email:
        return ResendEmailClient(api_key=api_key, from_email=from_email, app_base_url=app_base_url)
    return DevEmailClient(app_base_url=app_base_url)
