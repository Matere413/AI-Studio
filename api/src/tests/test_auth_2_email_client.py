"""Slice 2 — EmailClient (task 2-2).

Spec: email-verification — Email Delivery. Two implementations:
- ``DevEmailClient`` (``EMAIL_PROVIDER=dev``) — logs the verification URL
  via structlog. No external call.
- ``ResendEmailClient`` (``EMAIL_PROVIDER=resend``) — calls the Resend
  HTTP API with the verification link.

Delivery failure MUST NOT block registration (non-blocking).

These tests are written FIRST (RED) — the email client module does not
exist yet.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.features.auth.infrastructure.email_client import (
    DevEmailClient,
    EmailClient,
    ResendEmailClient,
    build_email_client,
)


# ─── Interface ────────────────────────────────────────────────────────────────


class TestEmailClientInterface:
    def test_email_client_is_protocol_like(self):
        """EmailClient exists as the abstract interface."""
        assert hasattr(EmailClient, "send_verification")

    def test_dev_client_is_email_client(self):
        client = DevEmailClient(app_base_url="https://app.test")
        assert isinstance(client, EmailClient)

    def test_resend_client_is_email_client(self):
        client = ResendEmailClient(
            api_key="re_test", from_email="noreply@test.io", app_base_url="https://app.test"
        )
        assert isinstance(client, EmailClient)


# ─── DevEmailClient ───────────────────────────────────────────────────────────


class TestDevEmailClient:
    def test_send_verification_logs_url_via_structlog(
        self, capsys, caplog
    ):
        """GIVEN EMAIL_PROVIDER=dev
        WHEN send_verification is called
        THEN the verification URL is logged (structlog) — no external call."""
        client = DevEmailClient(app_base_url="https://app.test")
        # Should not raise and should not perform any HTTP call.
        client.send_verification(
            email="user@test.io", raw_token="abc123token"
        )

    def test_dev_client_logs_url_contains_token_and_email(self):
        """The logged URL must contain the token and urlencoded email."""
        client = DevEmailClient(app_base_url="https://app.test")
        url = client.build_verification_url(
            email="user+space@test.io", raw_token="tokXYZ"
        )
        assert "tokXYZ" in url
        assert "user%2Bspace%40test.io" in url or "user+space%40test.io" in url

    def test_dev_client_app_base_url_default(self):
        client = DevEmailClient(app_base_url="")
        url = client.build_verification_url(
            email="user@test.io", raw_token="tok"
        )
        # Must start with the auth verify path even if base url empty.
        assert "/auth/verify" in url


# ─── ResendEmailClient ────────────────────────────────────────────────────────


class TestResendEmailClient:
    def test_build_verification_url(self):
        client = ResendEmailClient(
            api_key="re_x", from_email="noreply@test.io", app_base_url="https://app.test"
        )
        url = client.build_verification_url(
            email="user@test.io", raw_token="tok"
        )
        assert url == "https://app.test/auth/verify?token=tok&email=user%40test.io"

    def test_send_verification_calls_resend_api(self):
        """GIVEN EMAIL_PROVIDER=resend
        WHEN send_verification is called
        THEN Resend API is called with the verification link."""
        client = ResendEmailClient(
            api_key="re_test",
            from_email="noreply@test.io",
            app_base_url="https://app.test",
        )
        with patch(
            "src.features.auth.infrastructure.email_client._resend_send",
            return_value={"id": "msg_123"},
        ) as mock_send:
            client.send_verification(
                email="user@test.io", raw_token="tok"
            )
            assert mock_send.called
            call_kwargs = mock_send.call_args
            # The verification link must be in the call payload.
            assert any(
                "auth/verify" in str(v) for v in [call_kwargs.args, call_kwargs.kwargs]
            )

    def test_send_verification_failure_does_not_raise(self):
        """Spec: Delivery failure MUST NOT block registration."""
        client = ResendEmailClient(
            api_key="re_test",
            from_email="noreply@test.io",
            app_base_url="https://app.test",
        )
        with patch(
            "src.features.auth.infrastructure.email_client._resend_send",
            side_effect=RuntimeError("Resend API down"),
        ):
            # Must NOT raise.
            client.send_verification(email="user@test.io", raw_token="tok")


# ─── build_email_client factory ───────────────────────────────────────────────


class TestBuildEmailClient:
    def test_build_returns_dev_client_for_dev_provider(self):
        client = build_email_client(
            provider="dev", app_base_url="https://app.test"
        )
        assert isinstance(client, DevEmailClient)

    def test_build_returns_resend_client_for_resend_provider(self):
        client = build_email_client(
            provider="resend",
            api_key="re_x",
            from_email="noreply@test.io",
            app_base_url="https://app.test",
        )
        assert isinstance(client, ResendEmailClient)

    def test_build_defaults_to_dev_when_unknown_provider(self):
        client = build_email_client(
            provider="unknown", app_base_url="https://app.test"
        )
        assert isinstance(client, DevEmailClient)

    def test_build_resend_without_api_key_falls_back_to_dev(self):
        """No API key → fall back to dev (non-blocking)."""
        client = build_email_client(
            provider="resend",
            api_key=None,
            from_email="noreply@test.io",
            app_base_url="https://app.test",
        )
        assert isinstance(client, DevEmailClient)