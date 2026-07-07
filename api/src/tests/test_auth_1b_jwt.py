"""Slice 1b — JWT service (task 1b-2).

Covers session-management spec: Access Token Validation — JWT HS256 signed
with ``JWT_SECRET``, ``exp = 15min``, payload ``{sub, email, email_verified,
iat, exp, jti}``, 60s clock-skew leeway. Validation rejects expired,
malformed, and signature-mismatched tokens.

These tests are written FIRST (RED) — the implementation
``src/features/auth/infrastructure/jwt_service.py`` does not exist yet.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
import pytest

from src.features.auth.infrastructure.jwt_service import (
    JWTService,
    AccessTokenError,
)


@dataclass(frozen=True)
class _FakeUser:
    """Minimal user shape the JWT service needs to issue a token."""

    id: str
    email: str
    email_verified: bool


@pytest.fixture
def jwt_service() -> JWTService:
    """A JWTService bound to a known test secret."""
    return JWTService(secret="test-secret-please-not-in-prod-xxx")


@pytest.fixture
def sample_user() -> _FakeUser:
    return _FakeUser(
        id="user-uuid-123",
        email="alice@test.io",
        email_verified=False,
    )


class TestIssueAccess:
    """issue_access MUST produce a valid HS256 JWT with the binding payload."""

    def test_issue_returns_string(self, jwt_service, sample_user):
        """GIVEN a user
        WHEN issue_access is called
        THEN it returns a non-empty string (the encoded JWT)."""
        token = jwt_service.issue_access(sample_user)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_issue_uses_hs256(self, jwt_service, sample_user):
        """GIVEN a freshly issued token
        WHEN its header is decoded
        THEN the algorithm is HS256 (binding)."""
        token = jwt_service.issue_access(sample_user)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"

    def test_payload_contains_required_claims(self, jwt_service, sample_user):
        """GIVEN a freshly issued token
        WHEN decoded (without verify, to inspect the payload)
        THEN the payload contains ``sub``, ``email``, ``email_verified``,
        ``iat``, ``exp``, ``jti`` (binding from design.md)."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
        )
        for claim in ("sub", "email", "email_verified", "iat", "exp", "jti"):
            assert claim in payload, f"missing required claim: {claim}"

    def test_sub_is_user_id(self, jwt_service, sample_user):
        """GIVEN a user with id
        WHEN issue_access is called
        THEN the ``sub`` claim equals the user's id."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["sub"] == sample_user.id

    def test_email_claim_copied(self, jwt_service, sample_user):
        """GIVEN a user with email
        WHEN issue_access is called
        THEN the ``email`` claim equals the user's email."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["email"] == sample_user.email

    def test_email_verified_claim_copied(self, jwt_service, sample_user):
        """GIVEN a user with email_verified
        WHEN issue_access is called
        THEN the ``email_verified`` claim equals the user's email_verified."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["email_verified"] is sample_user.email_verified

    def test_exp_is_15_minutes_after_iat(self, jwt_service, sample_user):
        """GIVEN a freshly issued token
        WHEN ``exp`` and ``iat`` are inspected
        THEN ``exp - iat`` is 15 minutes (900s) within 1s tolerance."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["exp"] - payload["iat"] == pytest.approx(900, abs=1)

    def test_jti_is_unique_per_token(self, jwt_service, sample_user):
        """GIVEN two issue_access calls for the same user
        WHEN their ``jti`` claims are compared
        THEN they differ (each token gets a unique jti)."""
        t1 = jwt_service.issue_access(sample_user)
        t2 = jwt_service.issue_access(sample_user)
        p1 = jwt.decode(t1, options={"verify_signature": False})
        p2 = jwt.decode(t2, options={"verify_signature": False})
        assert p1["jti"] != p2["jti"], "jti must be unique per token"


class TestDecode:
    """decode() validates signature + expiry with 60s leeway."""

    def test_decode_valid_token_returns_payload(self, jwt_service, sample_user):
        """GIVEN a freshly issued token
        WHEN decoded
        THEN the payload is returned with all claims."""
        token = jwt_service.issue_access(sample_user)
        payload = jwt_service.decode(token)
        assert payload["sub"] == sample_user.id
        assert payload["email"] == sample_user.email
        assert payload["email_verified"] is sample_user.email_verified

    def test_decode_rejects_bad_signature(self, jwt_service, sample_user):
        """GIVEN a token signed with a different secret
        WHEN decoded with our service
        THEN AccessTokenError is raised (per session-management spec:
        bad-signature rejected)."""
        wrong = JWTService(secret="a-completely-different-secret-yyy")
        token = wrong.issue_access(sample_user)
        with pytest.raises(AccessTokenError):
            jwt_service.decode(token)

    def test_decode_rejects_malformed_token(self, jwt_service):
        """GIVEN a token that is not a valid JWT
        WHEN decoded
        THEN AccessTokenError is raised."""
        with pytest.raises(AccessTokenError):
            jwt_service.decode("not.a.valid.jwt")

    def test_decode_rejects_empty_token(self, jwt_service):
        """GIVEN an empty string
        WHEN decoded
        THEN AccessTokenError is raised (no token present)."""
        with pytest.raises(AccessTokenError):
            jwt_service.decode("")

    def test_decode_rejects_expired_token(self, jwt_service, sample_user):
        """GIVEN a token past ``exp`` + 60s leeway
        WHEN decoded
        THEN AccessTokenError is raised (session-management: expired rejected).

        We forge a token with ``exp`` far in the past so even with 60s leeway
        it is expired.
        """
        now = int(time.time())
        payload = {
            "sub": sample_user.id,
            "email": sample_user.email,
            "email_verified": False,
            "iat": now - 3600,
            "exp": now - 120,  # 120s ago → past the 60s leeway
            "jti": "stale-jti-xyz",
        }
        stale = jwt.encode(payload, "test-secret-please-not-in-prod-xxx", algorithm="HS256")
        with pytest.raises(AccessTokenError):
            jwt_service.decode(stale)

    def test_decode_accepts_token_within_leeway(self, jwt_service, sample_user):
        """GIVEN a token whose ``exp`` is <60s in the past
        WHEN decoded with the 60s leeway
        THEN it succeeds (leeway tolerates clock skew)."""
        now = int(time.time())
        payload = {
            "sub": sample_user.id,
            "email": sample_user.email,
            "email_verified": False,
            "iat": now - 60,
            "exp": now - 5,  # 5s ago → within 60s leeway
            "jti": "leeway-jti",
        }
        within = jwt.encode(payload, "test-secret-please-not-in-prod-xxx", algorithm="HS256")
        # Must not raise.
        payload_decoded = jwt_service.decode(within)
        assert payload_decoded["sub"] == sample_user.id


class TestJWTServiceSecret:
    """The service MUST be constructed with an explicit secret."""

    def test_empty_secret_rejected(self):
        """GIVEN an empty secret string
        WHEN JWTService is constructed
        THEN it raises (defence in depth — config boot guard is the primary
        gate, but the service should not silently accept an empty secret)."""
        with pytest.raises(ValueError):
            JWTService(secret="")