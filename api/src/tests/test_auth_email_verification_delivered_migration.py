"""Focused coverage for the email-verification delivery migration."""

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.shared.models.persistence import (
    async_session_factory,
    close_db,
    ensure_email_verification_delivered_column,
    init_db,
)


def _legacy_schema() -> tuple[str, str]:
    return (
        "CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE, "
        "password_hash VARCHAR(255) NOT NULL, email_verified BOOLEAN NOT NULL DEFAULT 0, "
        "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, last_login_at DATETIME)",
        "CREATE TABLE email_verifications (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, "
        "token_hash VARCHAR(255) NOT NULL UNIQUE, expires_at DATETIME NOT NULL, "
        "consumed_at DATETIME, created_at DATETIME NOT NULL)",
    )


async def _column_names(engine) -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {column["name"] for column in inspect(sync_conn).get_columns("email_verifications")}
        )


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'delivery-state.db'}"


async def test_init_db_migrates_legacy_sqlite_idempotently(database_url):
    engine = create_async_engine(database_url)
    users, verifications = _legacy_schema()
    async with engine.begin() as conn:
        await conn.execute(text(users))
        await conn.execute(text(verifications))
        await conn.execute(text(
            "INSERT INTO email_verifications "
            "(id, user_id, token_hash, expires_at, created_at) VALUES "
            "('challenge', 'user', 'hash', '2030-01-01', '2026-01-01')"
        ))
    await engine.dispose()

    engine = await init_db(database_url)
    try:
        assert "delivered" in await _column_names(engine)
        async with async_session_factory(engine)() as session:
            assert bool((await session.execute(text(
                "SELECT delivered FROM email_verifications WHERE id = 'challenge'"
            ))).scalar()) is False
            await ensure_email_verification_delivered_column(session)
            await session.commit()
    finally:
        await close_db()


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value

    def fetchall(self):
        return []


class _Session:
    def __init__(self, dialect: str, *, exists=False, error=None):
        self.bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": dialect})()})()
        self.exists, self.error, self.sql, self.rolled_back = exists, error, [], False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.sql.append(sql)
        if "information_schema.columns" in sql or "PRAGMA table_info" in sql:
            return _Result(1 if self.exists else None)
        if self.error:
            raise self.error
        return _Result()

    async def rollback(self):
        self.rolled_back = True


async def test_postgresql_branch_uses_not_null_default_false():
    session = _Session("postgresql")
    await ensure_email_verification_delivered_column(session)
    assert "ADD COLUMN delivered BOOLEAN NOT NULL DEFAULT FALSE" in session.sql[-1]


@pytest.mark.parametrize(
    ("dialect", "error"),
    [
        ("sqlite", Exception("duplicate column name: delivered")),
        ("postgresql", Exception('column "delivered" already exists')),
    ],
)
async def test_duplicate_column_race_is_idempotent(dialect, error):
    session = _Session(dialect, error=error)
    await ensure_email_verification_delivered_column(session)
    assert session.rolled_back is True
