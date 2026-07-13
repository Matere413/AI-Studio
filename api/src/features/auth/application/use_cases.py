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
from datetime import datetime, timezone

from src.shared.logging import get_logger

_log = get_logger(__name__)

from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy import select
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.orm import sessionmaker as _sync_sessionmaker

from src.features.auth.application.current_user import CurrentUser
from src.features.auth.application.ports import DeliveredChallengeQuery
from src.features.auth.infrastructure.jwt_service import JWTService
from src.features.auth.infrastructure.models import User
from src.features.auth.infrastructure.password_hasher import Argon2Hasher, DUMMY_HASH
from src.features.auth.infrastructure.refresh_store import RefreshTokenStore
from src.features.auth.infrastructure.email_client import EmailClient
from src.features.auth.infrastructure.email_verification_store import (
    EmailVerificationStore,
)
from src.shared.errors_auth import (
    AlreadyVerifiedError,
    EmailNotVerifiedError,
    EmailTakenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    TokenAlreadyConsumedError,
    TokenExpiredError,
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
    email_verification_store: EmailVerificationStore | None = None,
    email_client: EmailClient | None = None,
    ua: str | None = None,
    ip: str | None = None,
) -> AuthSession:
    """Create a new user account and issue an auth session.

    Also triggers an email-verification token (slice 2): mints a 32-byte
    random token, stores its argon2id hash + 24h expiry, and sends the
    verification email. The email send is non-blocking (failures are
    caught + logged inside the client). When ``email_verification_store``
    or ``email_client`` is None (slice 1b context), the verification
    step is skipped.

    Args:
        email: The registration email (validated for non-emptiness; uniqueness
            is enforced by the DB unique constraint).
        password: The plaintext password (strength-validated first).
        session_factory: The async session factory (used to insert the User).
        jwt_service: The JWT service (issues the access token).
        refresh_store: The refresh token store (persists the refresh row).
        email_verification_store: The verification token store (slice 2).
            When None, no verification row is created.
        email_client: The email delivery client (slice 2). When None, no
            email is sent.
        ua: Optional User-Agent string captured from the issuing request.
        ip: Optional client IP captured from the issuing request.

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

    # Slice 2: trigger email verification (non-blocking).
    _trigger_verification_email(
        user_id=user_id,
        email=email,
        email_verification_store=email_verification_store,
        email_client=email_client,
    )

    # Issue tokens (CPU-bound, sync) + persist the refresh row.
    current = CurrentUser(id=user_id, email=email, email_verified=email_verified)
    access_jwt = jwt_service.issue_access(current)
    refresh = refresh_store.create(user_id=user_id, ua=ua, ip=ip)

    return AuthSession(user=current, access_jwt=access_jwt, refresh_raw=refresh["raw_token"])


# ─── email verification trigger ────────────────────────────────────────────────


def _trigger_verification_email(
    *,
    user_id: str,
    email: str,
    email_verification_store: EmailVerificationStore | None,
    email_client: EmailClient | None,
) -> None:
    """Mint a verification token + send the verification email.

    Non-blocking: a None store or client is a no-op (slice 1b context).
    Email delivery failure is caught + logged inside the client.
    """
    if email_verification_store is None or email_client is None:
        return
    result = email_verification_store.create(user_id=user_id)
    token_id = result["token_id"]
    raw_token = result["raw_token"]
    send_result = email_client.send_verification(
        email=email, raw_token=raw_token, delivery_id=token_id
    )
    _record_delivery_outcome(email_verification_store, token_id, send_result)


def _record_delivery_outcome(
    email_verification_store: EmailVerificationStore, token_id: str, send_result
) -> None:
    """Persist only known delivery outcomes; uncertain sends remain pending."""
    if send_result.definitive:
        email_verification_store.mark_delivered(token_id, delivered=send_result.success)


# ─── login ───────────────────────────────────────────────────────────────────


def login_user(
    *,
    email: str,
    password: str,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    ua: str | None = None,
    ip: str | None = None,
    x_session_id: str | None = None,
) -> AuthSession:
    """Verify credentials and issue an auth session.

    Timing-attack mitigation (binding from design.md):
        On email-not-found, run ``argon2id.verify(DUMMY_HASH, password)`` to
        burn the same wall-clock time as a real wrong-password verify, then
        raise ``InvalidCredentialsError``. Both branches (missing email vs
        wrong password) return ``401 invalid_credentials`` with
        indistinguishable timing — preventing email enumeration via timing.

    Anonymous → authenticated project merge (slice 2):
        When ``x_session_id`` is provided AND credentials are valid, every
        project where ``session_id == x_session_id`` AND ``owner_id IS
        NULL`` is reassigned to ``owner_id = user.id``. One-time merge —
        projects created AFTER login are not merged. Spec:
        workspace-projects Anonymous-to-Authenticated Project Merge.

    Args:
        ua: Optional User-Agent string captured from the issuing request.
        ip: Optional client IP captured from the issuing request.
        x_session_id: The client's current ``X-Session-ID`` header. When
            present + credentials valid, anonymous projects bound to this
            session are claimed by the user.

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
        user.last_login_at = datetime.now(timezone.utc)
        session.commit()

    # Slice 2: claim anonymous projects bound to the client's session.
    if x_session_id:
        _merge_anonymous_projects(
            sync_factory=sync_factory,
            user_id=user_id,
            x_session_id=x_session_id,
        )

    current = CurrentUser(
        id=user_id, email=user_email, email_verified=user_verified
    )
    access_jwt = jwt_service.issue_access(current)
    refresh = refresh_store.create(user_id=user_id, ua=ua, ip=ip)

    return AuthSession(user=current, access_jwt=access_jwt, refresh_raw=refresh["raw_token"])


# ─── anonymous → authenticated project merge (slice 2) ────────────────────────


def _merge_anonymous_projects(
    *,
    sync_factory,
    user_id: str,
    x_session_id: str,
) -> int:
    """Reassign anonymous projects (owner_id IS NULL, session_id matches)
    to ``owner_id = user_id``. One-time merge.

    Returns the number of projects claimed (best-effort; not asserted).
    """
    from src.shared.models.persistence import Project

    with sync_factory() as session:
        stmt = (
            select(Project)
            .where(Project.session_id == x_session_id)
            .where(Project.owner_id.is_(None))
        )
        projects = session.scalars(stmt).all()
        for p in projects:
            p.owner_id = user_id
        session.commit()
        return len(projects)


# ─── refresh ─────────────────────────────────────────────────────────────────


def refresh_session(
    *,
    raw_refresh: str,
    session_factory,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    ua: str | None = None,
    ip: str | None = None,
) -> AuthSession:
    """Rotate a refresh token: revoke old, issue a new access + refresh pair.

    Atomicity: the row-count guard in ``RefreshTokenStore.revoke`` makes
    concurrent rotations deterministic — exactly one wins, the other gets
    ``revoke() == False`` and we raise ``InvalidRefreshTokenError``.

    Args:
        ua: Optional User-Agent string captured from the issuing request.
        ip: Optional client IP captured from the issuing request.

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
    refresh = refresh_store.create(user_id=user_id, ua=ua, ip=ip)

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


# ─── verify_email (slice 2) ───────────────────────────────────────────────────


def verify_email(
    *,
    email: str,
    token: str,
    session_factory,
    email_verification_store: EmailVerificationStore,
    hasher: Argon2Hasher | None = None,
) -> dict:
    """Verify an email-verification token + mark the user verified.

    Binding (design.md): the lookup is ``user_id``-scoped via the email.
    No user → ``invalid_token`` (anti-enumeration — same code as no-match).
    Then iterate the user's verification rows with NO prefilter on
    consumed/expired; for each row, ``argon2id.verify(row.token_hash,
    token)``:
        - match + consumed_at IS NOT NULL → ``token_already_consumed``
        - match + expires_at <= now → ``token_expired``
        - match + valid → atomic consume (set consumed_at = now, set
          users.email_verified = TRUE) → return ``{verified: True, user:
          {id, email, email_verified}}`` (4R CRITICAL 2 — the frontend
          needs the live user object to update its auth context without
          a second GET /auth/me). BREAK.
        - no match → continue
    No match on any row → ``invalid_token``.

    Raises:
        InvalidTokenError: No user OR no row matches.
        TokenAlreadyConsumedError: A matching row is already consumed.
        TokenExpiredError: A matching row is past expiry.
    """
    if not email or not token:
        raise InvalidTokenError()

    sync_factory = _derive_sync_factory(session_factory)
    _hasher = hasher or Argon2Hasher()

    # Resolve the user by email (no user → invalid_token, anti-enumeration).
    with sync_factory() as session:
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            raise InvalidTokenError()
        user_id = user.id

    # NO-prefilter scan: fetch ALL of the user's verification rows.
    rows = email_verification_store.find_by_user(user_id=user_id)
    now = datetime.now(timezone.utc)

    for row in rows:
        if not _hasher.verify(row["token_hash"], token):
            continue
        # Match found — classify.
        if row["consumed_at"] is not None:
            raise TokenAlreadyConsumedError()
        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise TokenExpiredError()
        # Valid — atomic consume + set users.email_verified = TRUE.
        # Judgment-day race fix: ``consume`` is atomic (WHERE consumed_at IS
        # NULL). A concurrent verify (or an ``invalidate_pending`` resend)
        # may have invalidated this row between the read above and the
        # consume. If ``consume`` returns False, THIS call lost the race —
        # do NOT set email_verified (the token is now consumed, so the user
        # cannot verify with it). Surface ``token_already_consumed`` so the
        # client knows to request a fresh challenge.
        consumed = email_verification_store.consume(row["id"])
        if not consumed:
            raise TokenAlreadyConsumedError()
        with sync_factory() as session:
            user = session.scalars(select(User).where(User.id == user_id)).first()
            if user is not None:
                user.email_verified = True
                session.commit()
        # 4R CRITICAL 2: return the LIVE user (email_verified=True post-verify)
        # so the frontend can hydrate its auth context from this response
        # without a second GET /auth/me round-trip.
        return {
            "verified": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "email_verified": bool(user.email_verified),
            },
        }

    # No row matched.
    raise InvalidTokenError()


# ─── resend_verification (slice 2) ─────────────────────────────────────────────


def resend_verification(
    *,
    user_id: str,
    session_factory,
    email_verification_store: EmailVerificationStore,
    email_client: EmailClient,
) -> None:
    """Issue a new verification token + send the email.

    Raises:
        AlreadyVerifiedError: When the user is already verified.
        InvalidTokenError: When the user no longer exists (defensive).
    """
    sync_factory = _derive_sync_factory(session_factory)
    with sync_factory() as session:
        user = session.scalars(select(User).where(User.id == user_id)).first()
        if user is None:
            raise InvalidTokenError()
        if user.email_verified:
            raise AlreadyVerifiedError()
        email = user.email

    # Replace old pending challenges atomically before sending the new token.
    result = email_verification_store.invalidate_and_create(user_id=user_id)
    token_id = result["token_id"]
    send_result = email_client.send_verification(
        email=email, raw_token=result["raw_token"], delivery_id=token_id
    )
    _record_delivery_outcome(email_verification_store, token_id, send_result)


# ─── save gate (delivery-aware email-verification policy) ─────────────────────


def enforce_save_gate(
    user: CurrentUser,
    delivered_challenge_query: DeliveredChallengeQuery | None,
) -> None:
    """Saving-gate policy: block an unverified user ONLY when a delivered
    verification challenge is on record.

    This is the application-layer authorization decision for the project-save
    gate (POST/PUT ``/projects``). The presentation layer resolves the
    authenticated user (``get_current_user`` → 401 for anonymous) and then
    calls this policy; the resulting ``EmailNotVerifiedError`` is mapped to
    ``403 email_not_verified`` by the global AppError handler. Authentication
    and project ownership remain fail-closed and are enforced independently
    (auth here-then-401; ownership in the AssetsService → ``NotOwnerError``).

    Hexagonal direction: the gate depends on the inward-facing
    :class:`DeliveredChallengeQuery` port (defined in the application layer),
    NOT on a concrete infrastructure store. Any object exposing
    ``has_delivered_challenge(user_id) -> bool`` satisfies the port
    structurally (the production ``EmailVerificationStore`` and test stubs
    alike).

    Policy contract (user-selected):
        - Verified user → passes (no block) regardless of challenge state.
        - Unverified + a DELIVERED challenge on record → RAISE
          ``EmailNotVerifiedError`` (the user received a challenge they have
          not completed — strict gate is legitimate).
        - Unverified + NO delivered challenge (failed send, uncertain send,
          outage, no challenge issued, store not wired, store query error) →
          DEGRADE to authenticated-only (no block). The user cannot complete
          a challenge they never received, so blocking would be a permanent
          deadlock with no path to verify. The email-verification gate is
          the ONLY gate that fails open here; auth and ownership stay
          fail-closed.

    Observability: every denied and degraded decision is logged via structlog
    with the decision + reason (+ error_type for store errors). No email,
    token, challenge detail, or user identifier fragment is logged — the
    events are privacy-safe bounded observability (no PII / stable user-id
    fragments in denial/degradation logs).

    Args:
        user: The authenticated user (``CurrentUser``).
        delivered_challenge_query: The wired delivered-challenge query port,
            or ``None`` (slice 1b / unwired context — gate degrades).

    Raises:
        EmailNotVerifiedError: When the user is unverified AND has a
            delivered challenge on record.
    """
    if user.email_verified:
        # Verified users pass the gate unconditionally; no decision to log.
        return

    query = delivered_challenge_query
    if query is None:
        _log.info(
            "save_gate_degraded",
            decision="degraded",
            reason="store_not_wired",
        )
        return

    try:
        delivered = query.has_delivered_challenge(user.id)
    except Exception as exc:  # noqa: BLE001 — gate MUST fail open on store error
        # The email-verification gate fails open on a store outage: the user
        # may have a delivered challenge we cannot confirm, but blocking them
        # with no path to verify is worse. Auth + ownership are NOT affected
        # (they are enforced elsewhere, fail-closed). Log the exception class
        # only — no message body (could carry DB identifiers) and no user-id
        # fragment (privacy-safe bounded observability).
        _log.warning(
            "save_gate_degraded",
            decision="degraded",
            reason="store_error",
            error_type=type(exc).__name__,
        )
        return

    if delivered:
        _log.info(
            "save_gate_denied",
            decision="denied",
            reason="delivered_challenge_unverified",
        )
        raise EmailNotVerifiedError()

    _log.info(
        "save_gate_degraded",
        decision="degraded",
        reason="no_delivered_challenge",
    )


__all__ = [
    "AuthSession",
    "enforce_save_gate",
    "login_user",
    "logout",
    "logout_all",
    "refresh_session",
    "register_user",
    "resend_verification",
    "validate_password_strength",
    "verify_email",
]
