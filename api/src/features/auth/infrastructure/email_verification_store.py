"""EmailVerificationStore — CRUD for single-use email-verification tokens.

Spec: email-verification — Token Generation + the verify-email lookup
contract from design.md.

The raw token is NEVER stored; only its argon2id hash (32-byte random
source, 24h expiry). Unlike ``RefreshTokenStore`` there is NO cleartext
``token_prefix`` on this table — the verify-email request carries the
user's ``email`` so the lookup is ``user_id``-scoped, then an iterate-and-
verify scan. ``find_by_user`` therefore returns ALL of the user's rows
with NO prefilter on ``consumed_at`` / ``expires_at`` — expired/consumed
rows that match the hash must be classifiable as ``token_expired`` /
``token_already_consumed`` (rather than filtered out and falling through
to ``invalid_token``).

The store is SYNC by design (argon2id hashing is CPU-bound, the SQL is
trivial). It derives a sync ``Session`` from the async factory's engine
URL, mirroring ``RefreshTokenStore``.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy import select, update
from sqlalchemy.orm import Session as _SyncSession
from sqlalchemy.orm import sessionmaker as _sync_sessionmaker

from src.shared.models.persistence import Base
from src.features.auth.infrastructure.models import EmailVerification
from src.features.auth.infrastructure.password_hasher import Argon2Hasher

_VERIFICATION_TTL_HOURS: int = 24
_RAW_TOKEN_BYTES: int = 32  # 256-bit random


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_sync_url(async_url: str) -> str:
    if "+aiosqlite" in async_url:
        return async_url.replace("+aiosqlite", "")
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    return async_url


class EmailVerificationStore:
    """CRUD for single-use, DB-hashed email-verification tokens.

    Args:
        session_factory: The async ``async_sessionmaker`` the rest of the
            app uses. The store derives a sync engine from the async
            engine's URL so its argon2id work runs off the event loop.
    """

    def __init__(self, session_factory) -> None:
        async_engine = session_factory.kw.get("bind") or session_factory.bind
        async_url = str(async_engine.url)
        sync_url = _to_sync_url(async_url)
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
        from src.features.auth.infrastructure import models as _auth_models  # noqa: F401

        with self._sync_engine.begin() as conn:
            Base.metadata.create_all(conn)
        self._sync_factory = _sync_sessionmaker(
            self._sync_engine, class_=_SyncSession, expire_on_commit=False
        )
        self._hasher = Argon2Hasher()

    # ── create ─────────────────────────────────────────────────────────────

    def create(self, user_id: str) -> dict:
        """Issue + persist a new verification token for ``user_id``.

        Mints a 32-byte random token, stores its argon2id hash + 24h
        expiry + ``consumed_at = None``, and returns the raw token ONCE
        (so the caller can build the verification URL / email). The raw
        token is NEVER stored.

        Returns:
            ``{"token_id": <row id>, "raw_token": <opaque raw token>}``.
        """
        raw_token = secrets.token_urlsafe(_RAW_TOKEN_BYTES)
        token_hash = self._hasher.hash(raw_token)
        expires_at = _utcnow() + timedelta(hours=_VERIFICATION_TTL_HOURS)

        with self._sync_factory() as session:
            row = EmailVerification(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {"token_id": row.id, "raw_token": raw_token}

    # ── find_by_user ───────────────────────────────────────────────────────

    def find_by_user(self, user_id: str) -> list[dict]:
        """Return ALL of the user's verification rows (newest first).

        Binding (design.md): NO prefilter on ``consumed_at`` or
        ``expires_at``. Expired/consumed rows that match the hash must be
        classifiable by the verify-email use case (token_expired /
        token_already_consumed) rather than filtered out.

        Returns a list of dicts with ``id``, ``user_id``, ``token_hash``,
        ``expires_at``, ``consumed_at``, ``created_at``.
        """
        if not user_id:
            return []
        with self._sync_factory() as session:
            stmt = (
                select(EmailVerification)
                .where(EmailVerification.user_id == user_id)
                .order_by(EmailVerification.created_at.desc())
            )
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "token_hash": r.token_hash,
                    "expires_at": r.expires_at,
                    "consumed_at": r.consumed_at,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── consume ────────────────────────────────────────────────────────────

    def consume(self, token_id: str) -> bool:
        """Atomically mark a verification row consumed (set ``consumed_at``).

        4R WARNING 2 — the UPDATE carries ``WHERE consumed_at IS NULL`` so
        a concurrent double-consume of the same token_id cannot both
        succeed. The row count tells us whether THIS call was the winner:
        ``True`` (1 row affected) or ``False`` (0 rows — already consumed
        or unknown token). The verify-email use case maps ``False`` to
        ``token_already_consumed`` when a matching row exists.

        Returns ``True`` when a row was updated, ``False`` otherwise.
        """
        now = _utcnow()
        with self._sync_factory() as session:
            stmt = (
                update(EmailVerification)
                .where(
                    EmailVerification.id == token_id,
                    EmailVerification.consumed_at.is_(None),
                )
                .values(consumed_at=now)
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount == 1


__all__ = ["EmailVerificationStore"]