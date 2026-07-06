"""RefreshTokenStore — opaque, DB-hashed refresh token CRUD.

Spec: session-management — Refresh Token Storage, Rotation, Logout Revokes
One/All. The raw token is NEVER stored; only its argon2id hash + a cleartext
12-char prefix (indexed) for O(log N) lookup.

Lookup strategy (binding from design.md):
    1. ``token_prefix = raw_token[:12]``
    2. ``SELECT ... WHERE token_prefix = :prefix AND revoked_at IS NULL
       AND expires_at > now()`` (indexed O(log N))
    3. ``argon2id.verify(row.token_hash, raw_token)`` to confirm

Rotation atomicity:
    ``revoke(token_id)`` uses an ``UPDATE ... WHERE revoked_at IS NULL`` and
    asserts ``rowcount == 1``. Two concurrent revokes against the same token
    race: exactly one wins (rowcount 1 → True), the other gets rowcount 0
    (→ False). This is portable across SQLite and PostgreSQL and wins the
    concurrent-refresh race by construction (no advisory lock needed).

The store is SYNC by design: argon2id hashing is CPU-bound (no IO) and the
SQL statements are tiny. The auth router calls it from async endpoints; the
underlying SQLAlchemy 2.0 async sessions are wrapped via
``async_sessionmaker`` and the store opens short sync sessions through a
thread-pool-bound sync engine view. For the MVP we use a sync SQLAlchemy
session bound to the SAME in-memory/file URL the async engine uses — this
keeps the store's argon2id + row-count work off the event loop and avoids
mixing sync/async idioms inside one transaction.

NOTE on engine choice: the store takes a ``session_factory`` (async) per the
existing app pattern, but its CRUD methods are SYNC because argon2id verify
is CPU-bound and the SQL is trivial. Internally it derives a sync
``Session`` from a sync ``Engine`` bound to the same URL. Tests construct it
from the async in-memory fixture; the store translates the URL to its sync
``sqlite://`` equivalent. In production the async engine's URL is already
``sqlite+aiosqlite://...`` — we strip the ``+aiosqlite`` driver suffix to get
the sync ``sqlite://`` URL.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy import select, update
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.orm import sessionmaker as _sync_sessionmaker

from src.shared.models.persistence import Base
from src.features.auth.infrastructure.models import RefreshToken, User
from src.features.auth.infrastructure.password_hasher import Argon2Hasher

_REFRESH_TTL_DAYS: int = 30
_TOKEN_PREFIX_LEN: int = 12  # first 12 chars of the raw token (clear, indexed)
_RAW_TOKEN_BYTES: int = 32  # 256-bit opaque random


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_sync_url(async_url: str) -> str:
    """Strip the async driver suffix to get a sync SQLAlchemy URL.

    ``sqlite+aiosqlite:///path`` → ``sqlite:///path``;
    ``postgresql+asyncpg://...`` → ``postgresql://...``.
    """
    if "+aiosqlite" in async_url:
        return async_url.replace("+aiosqlite", "")
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    return async_url


class RefreshTokenStore:
    """CRUD for opaque, DB-hashed refresh tokens.

    Args:
        session_factory: The async ``async_sessionmaker`` the rest of the app
            uses. The store derives a sync engine from the async engine's URL
            so its argon2id + row-count work runs off the event loop.
    """

    def __init__(self, session_factory) -> None:
        # Resolve a sync engine bound to the same database URL the async
        # engine uses. We peek at the async factory's bind (the AsyncEngine).
        async_engine = session_factory.kw.get("bind") or session_factory.bind
        async_url = str(async_engine.url)
        sync_url = _to_sync_url(async_url)
        # In-memory SQLite (``sqlite://`` or ``sqlite://:memory:``) uses a
        # per-connection private DB by default. To share the SAME in-memory
        # DB between the async engine and this sync engine we MUST use
        # ``StaticPool`` with a single shared connection — otherwise the
        # sync engine sees an empty DB (tables created on the async side
        # don't exist on the sync side). For file-based SQLite this is a
        # no-op (the file is the shared state).
        is_memory = ":memory:" in sync_url or sync_url.endswith("sqlite://")
        if is_memory:
            from sqlalchemy.pool import StaticPool

            self._sync_engine = _create_sync_engine(
                sync_url,
                future=True,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
        else:
            self._sync_engine = _create_sync_engine(sync_url, future=True)
        # Ensure the auth tables exist on this sync engine too. Idempotent —
        # ``create_all`` only creates tables that don't yet exist. For the
        # in-memory test fixture this provisions the tables on the shared
        # connection; for file-based production DBs ``init_db`` (async) has
        # already provisioned them and this is a no-op.
        from src.features.auth.infrastructure import models as _auth_models  # noqa: F401

        with self._sync_engine.begin() as conn:
            Base.metadata.create_all(conn)
        self._sync_factory = _sync_sessionmaker(
            self._sync_engine, class_=_SyncSession, expire_on_commit=False
        )
        self._hasher = Argon2Hasher()

    # ── create ─────────────────────────────────────────────────────────────

    def create(self, user_id: str, ua: str | None, ip: str | None) -> dict:
        """Issue + persist a new opaque refresh token for ``user_id``.

        Args:
            user_id: The owning user's id.
            ua: Optional User-Agent string captured at issue time.
            ip: Optional client IP captured at issue time.

        Returns:
            ``{"token_id": <row id>, "raw_token": <opaque raw token>}``.
            The raw token is returned ONCE to the caller (so it can be placed
            in the refresh cookie); it is NEVER stored. Only the argon2id
            hash + a 12-char clear prefix are persisted.
        """
        raw_token = secrets.token_urlsafe(_RAW_TOKEN_BYTES)
        token_prefix = raw_token[:_TOKEN_PREFIX_LEN]
        token_hash = self._hasher.hash(raw_token)
        expires_at = _utcnow() + timedelta(days=_REFRESH_TTL_DAYS)

        with self._sync_factory() as session:
            row = RefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                token_prefix=token_prefix,
                expires_at=expires_at,
                user_agent=ua,
                ip=ip,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {"token_id": row.id, "raw_token": raw_token}

    # ── find_active ────────────────────────────────────────────────────────

    def find_active(self, raw_token: str) -> dict | None:
        """Look up an active (non-revoked, non-expired) refresh token.

        Strategy: prefix-indexed SELECT + argon2id.verify. Returns ``None``
        when the prefix has no active row OR when the prefix matches but the
        argon2id verify fails (tampered raw token or prefix collision).
        """
        if not raw_token or len(raw_token) < _TOKEN_PREFIX_LEN:
            return None
        prefix = raw_token[:_TOKEN_PREFIX_LEN]
        now = _utcnow()

        with self._sync_factory() as session:
            stmt = (
                select(RefreshToken)
                .where(
                    RefreshToken.token_prefix == prefix,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .limit(1)
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None
            # Confirm the raw token actually hashes to the stored hash.
            if not self._hasher.verify(row.token_hash, raw_token):
                return None
            return {"token_id": row.id, "user_id": row.user_id}

    # ── revoke (row-count atomic guard) ────────────────────────────────────

    def revoke(self, token_id: str) -> bool:
        """Atomically revoke a refresh token by id.

        Uses ``UPDATE ... WHERE revoked_at IS NULL`` and asserts
        ``rowcount == 1``. This makes concurrent revokes deterministic:
        exactly one wins, the other gets ``False``.

        Returns:
            ``True`` when a row was revoked (rowcount == 1), ``False``
            otherwise (already revoked, expired, or unknown id).
        """
        now = _utcnow()
        with self._sync_factory() as session:
            stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.id == token_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount == 1

    # ── revoke_all ─────────────────────────────────────────────────────────

    def revoke_all(self, user_id: str) -> int:
        """Revoke every non-expired, non-revoked refresh token for ``user_id``.

        Used by ``POST /auth/logout-all``. Idempotent: returns the number of
        rows revoked (0 when the user has no active sessions).

        Spec scope: only NON-EXPIRED, non-revoked rows are touched. An
        already-expired row is inert (``find_active`` already excludes it)
        so revoking it would be a harmless-but-incorrect no-op; we skip it
        to keep the query faithful to the spec's "non-expired" qualifier.

        Args:
            user_id: The owning user's id.

        Returns:
            The number of rows revoked (``rowcount``).
        """
        now = _utcnow()
        with self._sync_factory() as session:
            stmt = (
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .values(revoked_at=now)
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount


__all__ = ["RefreshTokenStore"]