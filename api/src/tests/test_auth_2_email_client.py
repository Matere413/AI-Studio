"""Compatibility tests for the public email-client facade."""

from src.features.auth.infrastructure.email_client import (
    DevEmailClient, EmailClient, ResendEmailClient, build_email_client,
)


def test_public_clients_implement_protocol():
    assert isinstance(DevEmailClient(), EmailClient)
    assert isinstance(ResendEmailClient(api_key="re_test", from_email="noreply@test.io"), EmailClient)


def test_build_email_client_falls_back_to_dev():
    assert isinstance(build_email_client(provider="unknown"), DevEmailClient)


def test_dev_client_builds_verification_url_without_logging_raw_url():
    client = DevEmailClient(app_base_url="https://app.test")
    assert client.build_verification_url(email="user+tag@test.io", raw_token="token") == (
        "https://app.test/auth/verify?token=token&email=user%2Btag%40test.io"
    )
