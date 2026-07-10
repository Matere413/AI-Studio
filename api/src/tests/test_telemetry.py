from __future__ import annotations
import sys; import pytest
from unittest.mock import MagicMock
from src.shared import telemetry
from src.shared.telemetry import *  # noqa: F403
RAW = tuple(f"redaction-marker-{index}" for index in range(4))
def sentry(monkeypatch, initialized=True):
    mock = MagicMock(); mock.is_initialized.return_value = initialized; monkeypatch.setitem(sys.modules, "sentry_sdk", mock); return mock
@pytest.fixture
def log(monkeypatch):
    mock = MagicMock(); monkeypatch.setattr(telemetry, "_log", mock); return mock
CASES = [(capture_delivery_failed, dict(provider="resend", failure_category="auth_error", timeout_ms=15000, token_prefix="tok12345"), EVENT_ID_DELIVERY_FAILED, "warning", {"provider": "resend", "failure_category": "auth_error"}), (capture_delivery_timeout, dict(provider="resend", timeout_ms=15000, token_prefix="tok12345", phase="running"), EVENT_ID_DELIVERY_TIMEOUT, "warning", {"provider": "resend", "failure_category": "timeout", "phase": "running"}), (capture_delivery_backpressure, dict(provider="resend", timeout_ms=15000, token_prefix="tok12345", reason="pool_saturated"), EVENT_ID_DELIVERY_BACKPRESSURE, "warning", {"provider": "resend", "failure_category": "backpressure", "reason": "pool_saturated"}), (capture_delivery_late_resolved, dict(provider="resend", late_success=True, token_prefix="tok12345"), EVENT_ID_DELIVERY_LATE_RESOLVED, "info", {"provider": "resend", "late_success": "True"})]
@pytest.mark.parametrize("capture,kwargs,event_id,level,tags", CASES)
def test_delivery_capture_is_safe_and_observable(monkeypatch, log, capture, kwargs, event_id, level, tags):
    sdk = sentry(monkeypatch); capture(**kwargs); scope = sdk.push_scope.return_value.__enter__.return_value; received = str(sdk.mock_calls)
    assert sdk.capture_message.call_args.kwargs["level"] == level and event_id in sdk.capture_message.call_args.args[0]
    assert {call.args[0]: call.args[1] for call in scope.set_tag.call_args_list}.items() >= {"event_id": event_id, **tags}.items()
    assert getattr(log, level).call_args.kwargs["event_id"] == event_id and not any(value in received for value in RAW)
@pytest.mark.parametrize("capture,kwargs,event_id,level,tags", CASES)
def test_delivery_capture_degrades_without_or_with_broken_sentry(monkeypatch, log, capture, kwargs, event_id, level, tags):
    sdk = sentry(monkeypatch, False); capture(**kwargs); assert not sdk.capture_message.called and getattr(log, level).called
    sdk = sentry(monkeypatch); sdk.capture_message.side_effect = RuntimeError("down"); capture(**kwargs); assert getattr(log, level).called
    sdk = sentry(monkeypatch); log.warning.side_effect = RuntimeError("down"); capture_delivery_failed(provider="resend", failure_category="unknown", timeout_ms=1, token_prefix="tok12345"); assert sdk.capture_message.called
def test_delivery_capture_tolerates_missing_sentry(monkeypatch, log): monkeypatch.setitem(sys.modules, "sentry_sdk", None); capture_delivery_failed(provider="resend", failure_category="unknown", timeout_ms=1, token_prefix="tok12345"); assert log.warning.called
@pytest.mark.parametrize("level,expected", [("warn", "warning"), ("critical", "info")])
def test_frontend_capture_is_safe_and_observable(monkeypatch, log, level, expected):
    sdk = sentry(monkeypatch); capture_frontend_event(name=EVENT_ID_BOOTSTRAP_TRANSIENT, fields={"code": "timeout", "token": RAW[0], "cookie": RAW[1], "email": RAW[2], "url": RAW[3], "token_prefix": "tok12345", "detail": "x" * 5000}, level=level); scope = sdk.push_scope.return_value.__enter__.return_value; extras = {call.args[0]: call.args[1] for call in scope.set_extra.call_args_list}
    assert sdk.capture_message.call_args.kwargs["level"] == expected and {call.args[0]: call.args[1] for call in scope.set_tag.call_args_list}.items() >= {"event_id": EVENT_ID_BOOTSTRAP_TRANSIENT, "source": "frontend"}.items()
    assert all(extras[key] == "[redacted]" for key in ("token", "cookie", "email", "url")) and extras["token_prefix"] == "tok12345" and len(extras["detail"]) == 512 and getattr(log, expected).called
def test_frontend_capture_degrades_without_or_with_broken_sentry(monkeypatch, log):
    sdk = sentry(monkeypatch, False); capture_frontend_event(name=EVENT_ID_BOOTSTRAP_TRANSIENT, fields={}, level="warn"); assert not sdk.capture_message.called and log.warning.called
    sdk = sentry(monkeypatch); sdk.capture_message.side_effect = RuntimeError("down"); capture_frontend_event(name=EVENT_ID_BOOTSTRAP_TRANSIENT, fields={}, level="warn"); assert log.warning.called
def test_frontend_capture_tolerates_logger_failure(monkeypatch, log): sdk = sentry(monkeypatch); log.warning.side_effect = RuntimeError("down"); capture_frontend_event(name=EVENT_ID_BOOTSTRAP_TRANSIENT, fields={}, level="warn"); assert sdk.capture_message.called
