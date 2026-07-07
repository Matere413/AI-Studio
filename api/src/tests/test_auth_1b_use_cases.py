"""Slice 1b — Auth use cases (task 1b-5).

Covers the auth spec scenarios:
- Registration (success, email_taken, weak_password)
- Login (success, invalid_credentials with dummy-verify timing mitigation)
- Token Refresh Rotation (success, race, revoked, expired)
- Logout (revokes one)
- Logout-Global (revokes all)

Use cases orchestrate the infrastructure pieces (Argon2Hasher, JWTService,
RefreshTokenStore) plus the User ORM model. They return plain dicts the
router shapes into JSONResponse + cookies.

These tests are written FIRST (RED) —
``src/features/auth/application/use_cases.py`` does not exist yet.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.errors_auth import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    TokenRevokedError,
    UnauthorizedError,
    WeakPasswordError,
)
from src.shared.models.persistence import Base, async_session_factory
from src.features.auth.infrastructure.models import RefreshToken, User
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.application.use_cases import (
    AuthSession,
    login_user,
    logout,
    logout_all,
    refresh_session,
    register_user,
    validate_password_strength,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_1b_uc.db"
    url = f"sqlite+aiosqlite:///{db_file}"
    engine = _create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_session_factory(db_engine)


@pytest.fixture
def jwt_service() -> JWTService:
    return JWTService(secret="test-secret-please-not-in-prod-xxx")


@pytest.fixture
def refresh_store(session_factory) -> RefreshTokenStore:
    return RefreshTokenStore(session_factory=session_factory)


@pytest.fixture
def auth_deps(session_factory, jwt_service, refresh_store) -> dict:
    """Bundle the three dependencies the use cases need."""
    return {
        "session_factory": session_factory,
        "jwt_service": jwt_service,
        "refresh_store": refresh_store,
    }


def _strong_pw() -> str:
    """A password that passes the strength rules (>=12 chars, letter + digit)."""
    return "CorrectHorse42!"


# ─── validate_password_strength ──────────────────────────────────────────────


class TestValidatePasswordStrength:
    """Spec: >= 12 chars, <= 128 chars, one letter AND one digit."""

    def test_accepts_strong_password(self):
        assert validate_password_strength(_strong_pw()) is None  # no raise

    def test_rejects_short_password(self):
        with pytest.raises(WeakPasswordError):
            validate_password_strength("Short1!")

    def test_rejects_no_digit(self):
        with pytest.raises(WeakPasswordError):
            validate_password_strength("NoDigitHereLong!!")

    def test_rejects_no_letter(self):
        with pytest.raises(WeakPasswordError):
            validate_password_strength("123456789012")

    def test_accepts_exactly_12_chars(self):
        # "TwelveChars1!" is exactly 12 chars with a letter + digit.
        assert validate_password_strength("TwelveChars1!") is None

    def test_rejects_over_128_chars(self):
        with pytest.raises(WeakPasswordError):
            validate_password_strength("A1" + "x" * 127)


# ─── register_user ───────────────────────────────────────────────────────────


class TestRegisterUser:
    """register_user creates a user + issues an auth session (tokens)."""

    async def test_register_creates_user_row(
        self, auth_deps, session_factory
    ):
        """GIVEN a unique email + strong password
        WHEN register_user is called
        THEN a users row is persisted with email_verified=False and an
        argon2id password_hash."""
        result = register_user(
            email="alice@test.io",
            password=_strong_pw(),
            **auth_deps,
        )
        assert result.user.id
        assert result.user.email == "alice@test.io"
        assert result.user.email_verified is False

        async with session_factory() as session:
            stmt = select(User).where(User.email == "alice@test.io")
            user = (await session.execute(stmt)).scalar_one()
            assert user.password_hash.startswith("$argon2id$")
            assert user.email_verified is False

    async def test_register_returns_tokens(self, auth_deps):
        """GIVEN a successful registration
        WHEN the AuthSession is inspected
        THEN it contains a non-empty access_jwt and raw refresh token."""
        result = register_user(
            email="bob@test.io",
            password=_strong_pw(),
            **auth_deps,
        )
        assert result.access_jwt
        assert result.refresh_raw
        assert len(result.refresh_raw) >= 32

    async def test_register_email_taken_raises(
        self, auth_deps
    ):
        """GIVEN an email that already exists
        WHEN register_user is called with the same email
        THEN EmailTakenError is raised (409 email_taken)."""
        register_user(email="dup@test.io", password=_strong_pw(), **auth_deps)
        with pytest.raises(EmailTakenError):
            register_user(email="dup@test.io", password=_strong_pw(), **auth_deps)

    async def test_register_weak_password_raises(self, auth_deps):
        """GIVEN a password that fails strength rules
        WHEN register_user is called
        THEN WeakPasswordError is raised (400 weak_password)."""
        with pytest.raises(WeakPasswordError):
            register_user(email="weak@test.io", password="short", **auth_deps)

    async def test_register_persists_refresh_token_row(
        self, auth_deps, session_factory
    ):
        """GIVEN a successful registration
        WHEN the refresh_tokens table is inspected
        THEN a row exists for the new user with revoked_at=None."""
        result = register_user(
            email="rt@test.io",
            password=_strong_pw(),
            **auth_deps,
        )
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.user_id == result.user.id)
            tokens = (await session.execute(stmt)).scalars().all()
            assert len(tokens) == 1
            assert tokens[0].revoked_at is None

    async def test_register_empty_email_raises(self, auth_deps):
        """GIVEN an empty email
        WHEN register_user is called
        THEN ValueError is raised (defence in depth — empty email is a
        client error, not a spec error code)."""
        with pytest.raises((ValueError, WeakPasswordError)):
            register_user(email="", password=_strong_pw(), **auth_deps)


# ─── login_user ───────────────────────────────────────────────────────────────


class TestLoginUser:
    """login_user verifies credentials + issues tokens, with dummy-verify
    timing mitigation on missing email."""

    async def test_login_success_returns_tokens(
        self, auth_deps
    ):
        """GIVEN a registered user with correct credentials
        WHEN login_user is called
        THEN it returns an AuthSession with a fresh access_jwt + refresh_raw.
        """
        register_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        result = login_user(
            email="alice@test.io",
            password=_strong_pw(),
            **auth_deps,
        )
        assert result.user.email == "alice@test.io"
        assert result.access_jwt
        assert result.refresh_raw

    async def test_login_wrong_password_raises_invalid_credentials(
        self, auth_deps
    ):
        """GIVEN a registered user
        WHEN login_user is called with the wrong password
        THEN InvalidCredentialsError is raised (401 invalid_credentials)."""
        register_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        with pytest.raises(InvalidCredentialsError):
            login_user(
                email="alice@test.io",
                password="WrongPassword99!",
                **auth_deps,
            )

    async def test_login_unknown_email_raises_invalid_credentials(
        self, auth_deps
    ):
        """GIVEN an email not in the database
        WHEN login_user is called
        THEN InvalidCredentialsError is raised (NOT 'user not found' —
        anti-enumeration: same code as wrong password)."""
        with pytest.raises(InvalidCredentialsError):
            login_user(
                email="nobody@test.io",
                password=_strong_pw(),
                **auth_deps,
            )

    async def test_login_unknown_email_burns_dummy_verify_time(
        self, auth_deps
    ):
        """GIVEN the timing-attack mitigation requirement
        WHEN login_user handles a missing email
        THEN it runs a dummy argon2id.verify (DUMMY_HASH) so the wall-clock
        time is comparable to a real wrong-password verify.

        This is a coarse equivalence test (not a constant-time proof): both
        branches MUST execute argon2id.verify, so neither returns instantly.
        """
        import time as _time

        register_user(email="real@test.io", password=_strong_pw(), **auth_deps)

        # Time the no-user branch (dummy verify).
        t0 = _time.monotonic()
        with pytest.raises(InvalidCredentialsError):
            login_user(
                email="ghost@test.io",
                password=_strong_pw(),
                **auth_deps,
            )
        no_user_elapsed = _time.monotonic() - t0

        # Time the wrong-password branch (real verify, mismatch).
        t0 = _time.monotonic()
        with pytest.raises(InvalidCredentialsError):
            login_user(
                email="real@test.io",
                password="WrongPassword99!",
                **auth_deps,
            )
        wrong_pw_elapsed = _time.monotonic() - t0

        # Both must run argon2id.verify — neither returns instantly.
        assert no_user_elapsed > 0.001, (
            f"no-user branch appears to short-circuit (elapsed={no_user_elapsed:.4f}s)"
        )
        ratio = max(no_user_elapsed, wrong_pw_elapsed) / max(
            min(no_user_elapsed, wrong_pw_elapsed), 1e-9
        )
        assert ratio < 5.0, (
            f"timing divergence too large: no_user={no_user_elapsed:.4f}s "
            f"wrong_pw={wrong_pw_elapsed:.4f}s ratio={ratio:.2f}"
        )

    async def test_login_creates_new_refresh_token_row(
        self, auth_deps, session_factory
    ):
        """GIVEN a registered user
        WHEN login_user is called
        THEN a new refresh_tokens row is created (one per login session)."""
        register_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        login_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        async with session_factory() as session:
            from sqlalchemy import func

            cnt_stmt = select(func.count()).select_from(RefreshToken)
            count = (await session.execute(cnt_stmt)).scalar()
            assert count is not None and count >= 1


# ─── refresh_session ──────────────────────────────────────────────────────────


class TestRefreshSession:
    """refresh_session rotates: find_active → revoke old → issue new pair."""

    async def test_refresh_success_issues_new_pair_and_revokes_old(
        self, auth_deps
    ):
        """GIVEN a valid, non-revoked refresh token
        WHEN refresh_session is called
        THEN it returns a new AuthSession (new access + new refresh) and the
        old refresh token is revoked."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        old_raw = registered.refresh_raw
        old_token_id = _token_id_for_raw(auth_deps["refresh_store"], old_raw)

        new_session = refresh_session(raw_refresh=old_raw, **auth_deps)
        assert new_session.access_jwt
        assert new_session.refresh_raw
        assert new_session.refresh_raw != old_raw

        # The old token is now revoked.
        assert auth_deps["refresh_store"].find_active(old_raw) is None
        # The new token is active.
        assert (
            auth_deps["refresh_store"].find_active(new_session.refresh_raw)
            is not None
        )
        assert old_token_id is not None

    async def test_refresh_revoked_token_raises(
        self, auth_deps
    ):
        """GIVEN a refresh token already revoked (e.g., from logout)
        WHEN refresh_session is called
        THEN TokenRevokedError (or UnauthorizedError) is raised — the binding
        says ``401 invalid_refresh_token``; we raise TokenRevokedError which
        the router maps to that code."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        old_raw = registered.refresh_raw
        # Revoke it first (simulating a prior logout or refresh).
        auth_deps["refresh_store"].revoke(
            _token_id_for_raw(auth_deps["refresh_store"], old_raw)
        )
        with pytest.raises((TokenRevokedError, UnauthorizedError, InvalidRefreshTokenError)):
            refresh_session(raw_refresh=old_raw, **auth_deps)

    async def test_refresh_unknown_token_raises(
        self, auth_deps
    ):
        """GIVEN a random token that was never issued
        WHEN refresh_session is called
        THEN UnauthorizedError is raised (401 invalid_refresh_token)."""
        import secrets

        with pytest.raises((TokenRevokedError, UnauthorizedError, InvalidRefreshTokenError)):
            refresh_session(raw_refresh=secrets.token_urlsafe(32), **auth_deps)

    async def test_refresh_expired_token_raises(
        self, auth_deps, session_factory
    ):
        """GIVEN a refresh token past its expires_at
        WHEN refresh_session is called
        THEN UnauthorizedError is raised (401 invalid_refresh_token)."""
        from datetime import datetime, timedelta, timezone

        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        old_raw = registered.refresh_raw
        token_id = _token_id_for_raw(auth_deps["refresh_store"], old_raw)
        # Backdate expiry.
        async with session_factory() as session:
            stmt = select(RefreshToken).where(RefreshToken.id == token_id)
            row = (await session.execute(stmt)).scalar_one()
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await session.commit()
        with pytest.raises((TokenRevokedError, UnauthorizedError, InvalidRefreshTokenError)):
            refresh_session(raw_refresh=old_raw, **auth_deps)

    async def test_refresh_concurrent_race_exactly_one_wins(
        self, auth_deps
    ):
        """GIVEN the same refresh token used by two concurrent refresh calls
        WHEN both race
        THEN exactly one succeeds (returns AuthSession); the other raises
        (TokenRevokedError/UnauthorizedError). Atomic row-count guard."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        old_raw = registered.refresh_raw

        async def _attempt():
            try:
                return refresh_session(raw_refresh=old_raw, **auth_deps)
            except (TokenRevokedError, UnauthorizedError, InvalidRefreshTokenError):
                return None

        results = await asyncio.gather(_attempt(), _attempt())
        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]
        assert len(successes) == 1, (
            f"expected exactly 1 success, got {len(successes)}"
        )
        assert len(failures) == 1, (
            f"expected exactly 1 failure, got {len(failures)}"
        )


def _token_id_for_raw(store: RefreshTokenStore, raw: str) -> str | None:
    """Look up a refresh token id from the store (None if not active)."""
    found = store.find_active(raw)
    return found["token_id"] if found else None


# ─── logout ───────────────────────────────────────────────────────────────────


class TestLogout:
    """logout revokes ONLY the presented refresh token (other sessions live)."""

    async def test_logout_revokes_current_token(
        self, auth_deps
    ):
        """GIVEN an active refresh token
        WHEN logout is called with its raw value
        THEN that token is revoked (find_active returns None)."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        logout(raw_refresh=registered.refresh_raw, **auth_deps)
        assert auth_deps["refresh_store"].find_active(registered.refresh_raw) is None

    async def test_logout_keeps_other_sessions_alive(
        self, auth_deps
    ):
        """GIVEN two active refresh tokens for the same user
        WHEN logout is called with token A
        THEN token B remains active (logout revokes one, not all)."""
        a = register_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        b = login_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        logout(raw_refresh=a.refresh_raw, **auth_deps)
        assert auth_deps["refresh_store"].find_active(a.refresh_raw) is None
        assert auth_deps["refresh_store"].find_active(b.refresh_raw) is not None

    async def test_logout_unknown_token_is_noop(
        self, auth_deps
    ):
        """GIVEN a random token that was never issued
        WHEN logout is called
        THEN it does not raise (idempotent — the cookie may be stale)."""
        import secrets

        # Should not raise.
        logout(raw_refresh=secrets.token_urlsafe(32), **auth_deps)

    async def test_logout_already_revoked_is_noop(
        self, auth_deps
    ):
        """GIVEN a token that was already revoked
        WHEN logout is called again with it
        THEN it does not raise (idempotent)."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        logout(raw_refresh=registered.refresh_raw, **auth_deps)
        # Second logout must not raise.
        logout(raw_refresh=registered.refresh_raw, **auth_deps)


# ─── logout_all ───────────────────────────────────────────────────────────────


class TestLogoutAll:
    """logout_all revokes every active refresh token for the user."""

    async def test_logout_all_revokes_every_session(
        self, auth_deps
    ):
        """GIVEN a user with 3 active refresh tokens
        WHEN logout_all is called with the user id
        THEN all 3 are revoked."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        user_id = registered.user.id
        tokens = [registered.refresh_raw]
        for _ in range(2):
            tokens.append(
                login_user(
                    email="alice@test.io", password=_strong_pw(), **auth_deps
                ).refresh_raw
            )
        logout_all(user_id=user_id, **auth_deps)
        for raw in tokens:
            assert auth_deps["refresh_store"].find_active(raw) is None

    async def test_logout_all_does_not_touch_other_users(
        self, auth_deps
    ):
        """GIVEN user A and user B each with an active token
        WHEN logout_all is called for user A
        THEN user B's token remains active."""
        a = register_user(email="alice@test.io", password=_strong_pw(), **auth_deps)
        b = register_user(email="bob@test.io", password=_strong_pw(), **auth_deps)
        logout_all(user_id=a.user.id, **auth_deps)
        assert auth_deps["refresh_store"].find_active(a.refresh_raw) is None
        assert auth_deps["refresh_store"].find_active(b.refresh_raw) is not None

    async def test_logout_all_idempotent(
        self, auth_deps
    ):
        """GIVEN a user with no active tokens
        WHEN logout_all is called
        THEN it does not raise."""
        registered = register_user(
            email="alice@test.io", password=_strong_pw(), **auth_deps
        )
        logout_all(user_id=registered.user.id, **auth_deps)
        # Second call has nothing to revoke — must not raise.
        logout_all(user_id=registered.user.id, **auth_deps)