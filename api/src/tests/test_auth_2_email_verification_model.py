"""Slice 2 — EmailVerification ORM model (task 2-1).

Spec: email-verification — Token Generation. The model stores ONLY the
argon2id hash of the 32-byte random token (raw token MUST NOT be stored),
a 24h expiry, and a nullable ``consumed_at``. There is NO cleartext
``token_prefix`` on this table (unlike ``refresh_tokens``) — lookup is
``user_id``-scoped via the verify request's ``email`` field, then an
iterate-and-verify scan (per design.md).

These tests are written FIRST (RED) — the ``EmailVerification`` model does
not exist yet in ``infrastructure/models.py``.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.auth.infrastructure.models import EmailVerification, User
from src.shared.models.persistence import Base, async_session_factory


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "auth_2_ev_model.db"
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
async def sample_user(session_factory):
    async with session_factory() as session:
        user = User(email="ev@test.io", password_hash="$argon2id$abc")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ─── Table + columns ───────────────────────────────────────────────────────────


class TestEmailVerificationModel:
    """EmailVerification ORM — columns, FK, defaults."""

    def test_table_name_is_email_verifications(self):
        assert EmailVerification.__tablename__ == "email_verifications"

    def test_columns_exist(self):
        cols = {c.name for c in sa_inspect(EmailVerification).columns}
        expected = {"id", "user_id", "token_hash", "expires_at", "consumed_at", "created_at"}
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_no_token_prefix_column(self):
        """Binding: EmailVerification has NO token_prefix (hash-only)."""
        cols = {c.name for c in sa_inspect(EmailVerification).columns}
        assert "token_prefix" not in cols

    def test_user_id_is_fk_to_users(self):
        fks = sa_inspect(EmailVerification).columns["user_id"].foreign_keys
        assert any(fk.target_fullname == "users.id" for fk in fks)

    def test_token_hash_is_indexed_and_unique(self):
        col = sa_inspect(EmailVerification).columns["token_hash"]
        assert col.unique is True
        assert col.index is True

    def test_consumed_at_is_nullable(self):
        col = sa_inspect(EmailVerification).columns["consumed_at"]
        assert col.nullable is True

    def test_expires_at_is_indexed(self):
        col = sa_inspect(EmailVerification).columns["expires_at"]
        assert col.index is True

    async def test_create_row_defaults_consumed_at_none(
        self, session_factory, sample_user
    ):
        """GIVEN a new EmailVerification row
        WHEN inserted with a hash + expiry
        THEN consumed_at defaults to None and created_at is set."""
        from datetime import datetime, timezone

        async with session_factory() as session:
            row = EmailVerification(
                user_id=sample_user.id,
                token_hash="$argon2id$hashed",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            assert row.consumed_at is None
            assert row.created_at is not None
            assert row.id

    async def test_user_id_indexed(self, session_factory, sample_user):
        """user_id should be indexed for the user-scoped lookup query."""
        col = sa_inspect(EmailVerification).columns["user_id"]
        assert col.index is True