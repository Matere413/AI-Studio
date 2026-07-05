"""Auth application use cases — orchestrate the auth feature end-to-end.

Each use case returns an :class:`AuthSession` (the user + fresh access +
refresh tokens) or raises a spec-defined ``AppError`` subclass. The router
calls these, then shapes the result into a JSONResponse + cookies.

Use cases are SYNC because the underlying infrastructure (Argon2Hasher,
RefreshTokenStore) is sync (argon2id is CPU-bound; the store uses a sync
engine to keep argon2 work off the event loop). The router awaits them via
``asyncio.to_thread`` so they don't block the event loop.

Spec coverage (auth + session-management):
- ``validate_password_strength`` — >= 12 chars, <= 128 chars, one letter + one
  digit. Raises ``WeakPasswordError`` (400 weak_password).
- ``register_user`` — creates a user (email_verified=False), issues tokens,
  persists a refresh row. Raises ``EmailTakenError`` (409 email_taken).
- ``login_user`` — verifies credentials. On missing email runs a DUMMY
  argon2id.verify to burn the same time as a real wrong-password verify,
  then raises ``InvalidCredentialsError`` (401 invalid_credentials —
  identical shape/timing for both branches, anti-enumeration).
- ``refresh_session`` — find_active → revoke old (row-count atomic) → issue
  new pair. Raises ``UnauthorizedError`` (401 invalid_refresh_token) on
  unknown/expired/revoked. Concurrent races lose to the row-count guard.
- ``logout`` — revoke the presented refresh token (idempotent).
- ``logout_all`` — revoke every active refresh token for the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy import select
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.orm import sessionmaker as _sync_sessionmaker

from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.password_hasher import Argon2Hasher, DUMMY_HASH
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.presentation.dependencies import CurrentUser
from src.shared.errors_auth import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UnauthorizedError,
    WeakPasswordError,
)

# Spec: >= 12 chars, <= 128 chars, one letter AND one digit.
_MIN_PASSWORD_LEN: int = 12
_MAX_PASSWORD_LEN: int = 128
_LETTER_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9]")
_EMAIL_MAX_LEN: int = 254  # RFC 5321


def _derive_sync_factory(session_factory):
    """Derive a sync ``sessionmaker`` bound to the same DB as ``session_factory``.

    The use cases are SYNC (argon2id + refresh-store row-count work are
    CPU-bound and run off the event loop). They open short sync sessions
    against a sync engine bound to the same URL as the async engine. For
    in-memory SQLite this uses ``StaticPool`` so the sync + async engines
    share the same in-memory DB; for file-based SQLite the file is the
    shared state (production path).
    """
    async_engine = session_factory.kw.get("bind") or session_factory.bind
    async_url = str(async_engine.url)
    sync_url = async_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    is_memory = ":memory:" in sync_url or sync_url.endswith("sqlite://")
    if is_memory:
        from sqlalchemy.pool import StaticPool

        sync_engine = _create_sync_engine(
            sync_url,
            future=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        sync_engine = _create_sync_engine(sync_url, future=True)
    return _sync_sessionmaker(
        sync_engine, class_=_SyncSession, expire_on_commit=False
    )


@dataclass(frozen=True)
class AuthSession:
    """The result of register/login/refresh: the user + fresh tokens.

    Attributes:
        user: The authenticated user (id, email, email_verified).
        access_jwt: A freshly signed HS256 access token (15min).
        refresh_raw: A freshly issued opaque refresh token (raw value). The
            caller places it in the refresh cookie; the server stores only
            its hash. Returned ONCE — never persisted in plaintext.
    """

    user: CurrentUser
    access_jwt: str
    refresh_raw: str


# ─── Password strength ────────────────────────────────────────────────────────


def validate_password_strength(password: str) -> None:
    """Validate password strength per the auth spec.

    Rules (binding):
        - length >= 12 and <= 128
        - contains at least one letter
        - contains at least one digit

    Raises:
        WeakPasswordError: When any rule fails (400 weak_password).
    """
    if not isinstance(password, str) or len(password) < _MIN_PASSWORD_LEN:
        raise WeakPasswordError()
    if len(password) > _MAX_PASSWORD_LEN:
        raise WeakPasswordError()
    if not _LETTER_RE.search(password):
        raise WeakPasswordError()
    if not _DIGIT_RE.search(password):
        raise WeakPasswordError()


# ─── register ─────────────────────────────────────────────────────────────────


def register_user(
    *,
    email: str,
    password: str,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
) -> AuthSession:
    """Create a new user account and issue an auth session.

    Args:
        email: The registration email (validated for non-emptiness; uniqueness
            is enforced by the DB unique constraint).
        password: The plaintext password (strength-validated first).
        session_factory: The async session factory (used to insert the User).
        jwt_service: The JWT service (issues the access token).
        refresh_store: The refresh token store (persists the refresh row).

    Raises:
        WeakPasswordError: When the password fails strength rules.
        EmailTakenError: When the email already exists in ``users``.
        ValueError: When the email is empty or too long.

    Returns:
        An :class:`AuthSession` with the new user + fresh tokens.
    """
    if not email or not email.strip() or len(email) > _EMAIL_MAX_LEN:
        raise ValueError("email is required and must be <= 254 chars")
    validate_password_strength(password)

    # Persist the user via a sync session derived from the same engine as the
    # async session_factory so we stay off the event loop for the argon2id
    # hash work. The refresh_store already derives its own sync engine; we
    # derive one here for the user insert.
    from src.shared.models.persistence import Base
    import src.features.auth.infrastructure.models  # noqa: F401

    sync_factory = _derive_sync_factory(session_factory)
    sync_engine = sync_factory.kw["bind"]
    # Ensure the auth tables exist on this sync engine too (idempotent; no-op
    # for the file-based production DB where init_db already provisioned them).
    with sync_engine.begin() as conn:
        Base.metadata.create_all(conn)

    hasher = Argon2Hasher()
    password_hash = hasher.hash(password)

    with sync_factory() as session:
        # Check uniqueness first so we can raise EmailTakenError cleanly
        # (the DB unique constraint would raise IntegrityError, but the
        # spec wants a 409 email_taken, not a 500).
        existing = session.scalars(
            select(User).where(User.email == email)
        ).first()
        if existing is not None:
            raise EmailTakenError()
        user = User(email=email, password_hash=password_hash, email_verified=False)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
        email_verified = user.email_verified

    # Issue tokens (CPU-bound, sync) + persist the refresh row.
    current = CurrentUser(id=user_id, email=email, email_verified=email_verified)
    access_jwt = jwt_service.issue_access(current)
    refresh = refresh_store.create(user_id=user_id, ua=None, ip=None)

    return AuthSession(user=current, access_jwt=access_jwt, refresh_raw=refresh["raw_token"])


# ─── login ───────────────────────────────────────────────────────────────────


def login_user(
    *,
    email: str,
    password: str,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
) -> AuthSession:
    """Verify credentials and issue an auth session.

    Timing-attack mitigation (binding from design.md):
        On email-not-found, run ``argon2id.verify(DUMMY_HASH, password)`` to
        burn the same wall-clock time as a real wrong-password verify, then
        raise ``InvalidCredentialsError``. Both branches (missing email vs
        wrong password) return ``401 invalid_credentials`` with
        indistinguishable timing — preventing email enumeration via timing.

    Raises:
        InvalidCredentialsError: For a non-existent email OR a wrong
            password (identical shape/timing).

    Returns:
        An :class:`AuthSession` with the user + fresh tokens.
    """
    sync_factory = _derive_sync_factory(session_factory)

    hasher = Argon2Hasher()
    with sync_factory() as session:
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            # Burn the same time as a real verify, then return the identical
            # error (anti-enumeration). The DUMMY_HASH verify always returns
            # False — we ignore the result.
            hasher.verify(DUMMY_HASH, password)
            raise InvalidCredentialsError()
        if not hasher.verify(user.password_hash, password):
            raise InvalidCredentialsError()
        user_id = user.id
        user_email = user.email
        user_verified = user.email_verified
        # Touch last_login_at (best-effort; not asserted in tests).
        from datetime import datetime, timezone

        user.last_login_at = datetime.now(timezone.utc)
        session.commit()

    current = CurrentUser(
        id=user_id, email=user_email, email_verified=user_verified
    )
    access_jwt = jwt_service.issue_access(current)
    refresh = refresh_store.create(user_id=user_id, ua=None, ip=None)

    return AuthSession(user=current, access_jwt=access_jwt, refresh_raw=refresh["raw_token"])


# ─── refresh ─────────────────────────────────────────────────────────────────


def refresh_session(
    *,
    raw_refresh: str,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
) -> AuthSession:
    """Rotate a refresh token: revoke old, issue a new access + refresh pair.

    Atomicity: the row-count guard in ``RefreshTokenStore.revoke`` makes
    concurrent rotations deterministic — exactly one wins, the other gets
    ``revoke() == False`` and we raise ``InvalidRefreshTokenError``.

    Raises:
        InvalidRefreshTokenError: When the raw token is unknown, expired,
            revoked, or loses a concurrent-rotation race
            (401 invalid_refresh_token). Every refresh failure returns the
            SAME code so a client cannot distinguish WHY it failed
            (anti-enumeration, consistent with login).

    Returns:
        A new :class:`AuthSession` with the user + fresh tokens. The old
        refresh token is revoked.
    """
    found = refresh_store.find_active(raw_refresh)
    if found is None:
        raise InvalidRefreshTokenError()
    token_id = found["token_id"]
    user_id = found["user_id"]

    # Atomic revoke. If this returns False, another concurrent refresh already
    # revoked the token — we lose the race.
    if not refresh_store.revoke(token_id):
        raise InvalidRefreshTokenError()

    # Load the user to issue a fresh access token + reflect current
    # email_verified from the DB.
    sync_factory = _derive_sync_factory(session_factory)
    with sync_factory() as session:
        user = session.scalars(select(User).where(User.id == user_id)).first()
        if user is None:
            raise InvalidRefreshTokenError()
        current = CurrentUser(
            id=user.id, email=user.email, email_verified=user.email_verified
        )

    access_jwt = jwt_service.issue_access(current)
    refresh = refresh_store.create(user_id=user_id, ua=None, ip=None)

    return AuthSession(user=current, access_jwt=access_jwt, refresh_raw=refresh["raw_token"])


# ─── logout ───────────────────────────────────────────────────────────────────


def logout(
    *,
    raw_refresh: str,
    session_factory=None,
    jwt_service: JWTService | None = None,
    refresh_store: RefreshTokenStore,
) -> None:
    """Revoke the presented refresh token (idempotent).

    Does NOT revoke other refresh tokens for the same user (logout revokes
    one, not all — see ``logout_all``). Does NOT raise on unknown / already-
    revoked tokens (the cookie may be stale or absent).

    ``session_factory`` and ``jwt_service`` are accepted for signature
    symmetry with the other use cases but are unused — logout only touches
    the refresh store.
    """
    found = refresh_store.find_active(raw_refresh)
    if found is None:
        # Unknown / expired / already revoked — nothing to revoke. Idempotent.
        return
    refresh_store.revoke(found["token_id"])


def logout_all(
    *,
    user_id: str,
    session_factory=None,
    jwt_service: JWTService | None = None,
    refresh_store: RefreshTokenStore,
) -> None:
    """Revoke every active refresh token for ``user_id``.

    Used by ``POST /auth/logout-all``. Idempotent (no-op when the user has
    no active sessions). Does not touch other users' tokens.

    ``session_factory`` and ``jwt_service`` are accepted for signature
    symmetry but are unused.
    """
    refresh_store.revoke_all(user_id)


__all__ = [
    "AuthSession",
    "login_user",
    "logout",
    "logout_all",
    "refresh_session",
    "register_user",
    "validate_password_strength",
]