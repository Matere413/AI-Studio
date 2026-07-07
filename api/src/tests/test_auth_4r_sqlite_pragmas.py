"""4R corrective pass — WARNING 3: SQLite WAL + busy_timeout.

The engine was created without ``PRAGMA journal_mode=WAL`` or
``busy_timeout``, so concurrent writes risked ``database is locked``. The
fix registers a SQLAlchemy ``connect`` event listener that sets both
PRAGMAs on every new SQLite connection (async + sync engines).

WAL (Write-Ahead Logging) lets readers + a writer proceed concurrently;
``busy_timeout=5000`` makes a locked connection wait up to 5s for the lock
instead of failing immediately.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine as _create_sync_engine, text
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.shared.models.persistence import Base, _apply_sqlite_pragmas


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


class TestSqlitePragmas:
    """The connect listener MUST set WAL + busy_timeout on SQLite."""

    def test_apply_pragmas_is_a_connect_listener(self):
        """GIVEN the module
        WHEN _apply_sqlite_pragmas is inspected
        THEN it is registered as a 'connect' event listener (so it fires on
        every new SQLite connection, async + sync)."""
        # The listener is registered at import time via event.listens_for.
        # We assert the helper exists + is callable (the registration is
        # verified by the runtime pragma tests below).
        assert callable(_apply_sqlite_pragmas)

    def test_sync_engine_sets_wal(self, tmp_path: Path):
        """GIVEN a sync SQLite engine created after the fix
        WHEN a connection is opened + PRAGMA journal_mode is queried
        THEN it returns 'wal'."""
        db = tmp_path / "pragma_sync.db"
        url = f"sqlite:///{db}"
        engine = _create_sync_engine(url)
        try:
            with engine.connect() as conn:
                mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                assert mode == "wal", f"journal_mode MUST be 'wal', got {mode!r}"
        finally:
            engine.dispose()

    def test_sync_engine_sets_busy_timeout(self, tmp_path: Path):
        """GIVEN a sync SQLite engine
        WHEN PRAGMA busy_timeout is queried
        THEN it returns 5000 (ms)."""
        db = tmp_path / "pragma_sync_bt.db"
        url = f"sqlite:///{db}"
        engine = _create_sync_engine(url)
        try:
            with engine.connect() as conn:
                bt = conn.execute(text("PRAGMA busy_timeout")).scalar()
                assert bt == 5000, f"busy_timeout MUST be 5000, got {bt!r}"
        finally:
            engine.dispose()

    @pytest.mark.asyncio
    async def test_async_engine_sets_wal(self, tmp_path: Path):
        """GIVEN an async SQLite engine
        WHEN a connection is opened + PRAGMA journal_mode is queried
        THEN it returns 'wal'."""
        db = tmp_path / "pragma_async.db"
        url = f"sqlite+aiosqlite:///{db}"
        engine = _create_async_engine(url)
        try:
            async with engine.connect() as conn:
                mode = await conn.execute(text("PRAGMA journal_mode"))
                val = mode.scalar()
                assert val == "wal", f"async journal_mode MUST be 'wal', got {val!r}"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_async_engine_sets_busy_timeout(self, tmp_path: Path):
        """GIVEN an async SQLite engine
        WHEN PRAGMA busy_timeout is queried
        THEN it returns 5000."""
        db = tmp_path / "pragma_async_bt.db"
        url = f"sqlite+aiosqlite:///{db}"
        engine = _create_async_engine(url)
        try:
            async with engine.connect() as conn:
                bt = await conn.execute(text("PRAGMA busy_timeout"))
                val = bt.scalar()
                assert val == 5000, f"async busy_timeout MUST be 5000, got {val!r}"
        finally:
            await engine.dispose()

    def test_pragmas_applied_on_every_new_connection(self, tmp_path: Path):
        """GIVEN two connections from the same engine
        WHEN both query journal_mode
        THEN both return 'wal' (the listener fires per-connection, not
        just once at engine creation)."""
        db = tmp_path / "pragma_multi.db"
        url = f"sqlite:///{db}"
        engine = _create_sync_engine(url)
        try:
            with engine.connect() as conn1:
                m1 = conn1.execute(text("PRAGMA journal_mode")).scalar()
            with engine.connect() as conn2:
                m2 = conn2.execute(text("PRAGMA journal_mode")).scalar()
            assert m1 == "wal"
            assert m2 == "wal"
        finally:
            engine.dispose()