"""SQLAlchemy 2.0 async ORM models for the auth feature.

Both models are registered on the shared :class:`src.shared.models.persistence.Base`
so ``Base.metadata.create_all`` provisions ``users`` and ``refresh_tokens``
alongside the existing ``projects`` and ``assets`` tables.

Schema (binding per design.md):

- ``User``: id, email (unique + indexed), password_hash (argon2id string),
  email_verified (bool, default False, server_default "0"), created_at,
  updated_at, last_login_at (nullable).
- ``RefreshToken``: id, user_id (FK users.id ON DELETE CASCADE), token_hash
  (argon2id, unique + indexed), token_prefix (clear first 12 chars, indexed for
  O(log N) lookup), expires_at (30d, indexed), revoked_at (nullable, indexed),
  last_used_at (nullable), user_agent (nullable), ip (nullable), created_at.

The raw refresh token is NEVER stored — only its argon2id hash + a cleartext
12-char prefix for indexed lookup. This is the standard opaque-rotation pattern.

``EmailVerification`` is added in slice 2 (task 2-1) — not here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.models.persistence import Base, _uuid_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (helper for column defaults)."""
    return datetime.now(timezone.utc)


class User(Base):
    """A registered account.

    Attributes:
        id: UUID primary key (string for SQLite compat).
        email: Unique, indexed login email (max 254 per RFC 5321).
        password_hash: argon2id hash string (``$argon2id$...``). Plaintext is
            NEVER stored or logged.
        email_verified: Whether the user has verified their email. Defaults to
            ``False``; ``server_default="0"`` so the DB provides it even on
            raw inserts (migration parity).
        created_at: Auto-set creation timestamp (UTC).
        updated_at: Auto-updated timestamp (UTC); set on creation and on update.
        last_login_at: Timestamp of the most recent successful login; ``None``
            until the first login.
    """

    __tablename__ = "users"

    id: Mapped[str] = _uuid_column()
    email: Mapped[str] = mapped_column(
        String(254), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r} verified={self.email_verified}>"


class RefreshToken(Base):
    """An opaque, DB-hashed refresh token (one row per login session).

    The raw token is NEVER stored. Lookup strategy:
        1. Extract ``token_prefix = raw_token[:12]``.
        2. ``SELECT ... WHERE token_prefix = :prefix AND revoked_at IS NULL
           AND expires_at > now()`` (indexed O(log N)).
        3. ``argon2id.verify(row.token_hash, raw_token)`` to confirm.

    Attributes:
        id: UUID primary key.
        user_id: FK to ``users.id`` (ON DELETE CASCADE).
        token_hash: argon2id hash of the raw token (unique + indexed).
        token_prefix: Cleartext first 12 chars of the raw token (indexed) for
            O(log N) prefix lookup.
        expires_at: Token expiry (now + 30d); indexed for expiry sweeps.
        revoked_at: When the token was revoked (logout / rotation); ``None``
            while active; indexed for ``revoked_at IS NULL`` queries.
        last_used_at: Last time the token was used for refresh; ``None`` until
            first use.
        user_agent: Optional User-Agent string captured at issue time.
        ip: Optional client IP captured at issue time.
        created_at: Auto-set creation timestamp (UTC).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = _uuid_column()
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id!r} user_id={self.user_id!r} "
            f"prefix={self.token_prefix!r} revoked={self.revoked_at is not None}>"
        )