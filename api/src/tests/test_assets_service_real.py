"""Real-DB integration tests for AssetsService (not mocked).

These tests exercise the actual service layer with a real in-memory SQLite
database, exposing vulnerabilities that mocked tests cannot detect:

1. **Path Traversal & Overwrites**: r2_key MUST use server-side UUID, not
   user-provided ``asset_name``.
2. **Detached Instance Safety**: Service returns dicts so the caller never
   accesses an expired SQLAlchemy ``AsyncSession``.
3. **Ghost Assets (Resilience)**: When ``presigned_put`` fails the DB must
   NOT retain an orphan Asset row.
4. **Structured Error Handling**: Custom exception classes replace stringly-typed
   ``ValueError`` codes so the router can map them to proper HTTP statuses.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine

from src.features.assets.exceptions import (
    AssetNotFoundError,
    ProjectNotFoundError,
    ProjectOwnershipError,
    StorageNotConfiguredError,
    StorageOperationError,
)
from src.features.assets.service import AssetsService
from src.shared.models.persistence import (
    Asset,
    Base,
    Project,
    active_assets,
    async_session_factory,
)
from src.shared.storage import R2Storage, StorageError


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def engine():
    """Create an isolated in-memory SQLite engine for each test session."""
    eng = _create_async_engine("sqlite+aiosqlite://", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.execute(text("PRAGMA foreign_keys=ON")))
        await conn.run_sync(Project.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Project.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db_session(engine):
    """Return a standalone AsyncSession for direct DB queries."""
    factory = async_session_factory(engine)
    async with factory() as session:
        yield session


@pytest.fixture
def session_factory(engine):
    """Return an ``async_sessionmaker`` bound to the test engine."""
    return async_session_factory(engine)


@pytest.fixture
async def real_service(session_factory):
    """Return an AssetsService bound to the real DB engine.

    Uses a no-op storage mock that returns a fake presigned URL so
    ``request_upload_ticket`` can be tested without real R2 credentials.
    """
    storage = AsyncMock(spec=R2Storage)
    storage.presigned_put.return_value = "https://r2.example.com/presigned-put-url"

    service = AssetsService(
        session_factory=session_factory,
        storage=storage,
    )
    return service


@pytest.fixture
async def sample_project(db_session):
    """Create and return a sample project."""
    project = Project(
        name="Campaign A",
        owner_id="user-abc",
        session_id="session-abc",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def real_service_no_storage(session_factory):
    """Return an AssetsService WITHOUT storage, to test 503."""
    return AssetsService(
        session_factory=session_factory,
        storage=None,
    )


# ==============================================================================
# Fix 1: Path Traversal — r2_key MUST use server-side UUID
# ==============================================================================


class TestPathTraversal:
    """``r2_key`` MUST be generated server-side, not from user-provided name."""

    async def test_r2_key_uses_uuid_not_asset_name(self, real_service, sample_project):
        """GIVEN an asset_name with path-traversal characters
        WHEN request_upload_ticket is called
        THEN the r2_key does NOT contain the user's asset_name.
        """
        malicious_name = "../../etc/passwd"
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name=malicious_name,
            session_id="session-abc",
        )

        assert "../../etc" not in ticket["r2_key"]
        assert malicious_name not in ticket["r2_key"]
        assert ticket["r2_key"].startswith(f"projects/{sample_project.id}/")

    async def test_r2_key_is_uuid_hex_format(self, real_service, sample_project):
        """GIVEN a valid request_upload_ticket call
        WHEN the ticket is returned
        THEN r2_key ends with a 32-char hex string (uuid4 hex).
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="portrait.webp",
            session_id="session-abc",
        )

        r2_suffix = ticket["r2_key"].split("/")[-1]
        # uuid4().hex produces a 32-char hex string
        assert len(r2_suffix) == 32
        assert all(c in "0123456789abcdef" for c in r2_suffix)

    async def test_asset_name_stored_in_db_not_in_key(self, real_service, sample_project, db_session):
        """GIVEN request_upload_ticket with a special asset_name
        WHEN the asset is persisted
        THEN ``name`` column stores the original name, but ``r2_key`` is UUID-based.
        """
        original_name = "my photo.webp"
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name=original_name,
            session_id="session-abc",
        )

        stmt = select(Asset).where(Asset.id == ticket["asset_id"])
        asset = await db_session.scalar(stmt)

        assert asset is not None
        assert asset.name == original_name  # Original name preserved in DB
        assert asset.r2_key != original_name  # Key is UUID, not the name


# ==============================================================================
# Fix 2: Detached Instance Safety — service returns dicts, not ORM objects
# ==============================================================================


class TestDetachedInstanceSafety:
    """Service MUST return plain dicts (or Pydantic DTOs), not SQLAlchemy ORM
    instances, so the caller never hits a ``DetachedInstanceError``."""

    async def test_create_project_returns_dict(self, real_service, db_session):
        """GIVEN create_project is called
        THEN the returned value is a dict, not an ORM model.
        """
        result = await real_service.create_project(
            name="Dict Project",
            session_id="session-dict",
        )
        assert isinstance(result, dict), "Expected dict, got ORM instance"

    async def test_list_projects_returns_dict_list(self, real_service, sample_project):
        """GIVEN list_projects is called
        THEN each item is a dict, not an ORM model.
        """
        results = await real_service.list_projects(session_id="session-abc")
        assert len(results) >= 1
        for p in results:
            assert isinstance(p, dict), f"Expected dict, got {type(p)}"

    async def test_request_upload_ticket_returns_dict(self, real_service, sample_project):
        """GIVEN request_upload_ticket is called
        THEN the returned value is a dict.
        """
        result = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="test.webp",
            session_id="session-abc",
        )
        assert isinstance(result, dict)

    async def test_finalize_asset_returns_dict(self, real_service, sample_project, db_session):
        """GIVEN finalize_asset is called
        THEN the returned value is a dict, not an ORM model.
        """
        # Create an asset first
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="finalize.webp",
            session_id="session-abc",
        )

        result = await real_service.finalize_asset(
            asset_id=ticket["asset_id"],
            session_id="session-abc",
        )
        assert isinstance(result, dict)

    async def test_project_dict_contains_assets_list(self, real_service, sample_project):
        """GIVEN a project has assets
        WHEN list_projects is called
        THEN the project dict includes an ``assets`` list.
        """
        # Create an asset
        await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="asset1.webp",
            session_id="session-abc",
        )

        results = await real_service.list_projects(session_id="session-abc")
        project = next(p for p in results if p["id"] == sample_project.id)
        assert "assets" in project
        assert isinstance(project["assets"], list)


# ==============================================================================
# Fix 3: Ghost Assets — no orphan rows when presigned URL generation fails
# ==============================================================================


class TestGhostAssetPrevention:
    """When ``presigned_put`` fails, the DB MUST NOT retain an Asset row."""

    async def test_no_ghost_asset_on_storage_failure(self, real_service, sample_project, db_session):
        """GIVEN presigned_put raises an exception
        WHEN request_upload_ticket is called
        THEN no Asset row exists in the database.
        """
        # Make storage fail
        real_service._storage.presigned_put.side_effect = StorageError("R2 unavailable")

        with pytest.raises(StorageOperationError):
            await real_service.request_upload_ticket(
                project_id=sample_project.id,
                asset_name="ghost.webp",
                session_id="session-abc",
            )

        # Verify no ghost Asset row
        stmt = select(Asset).where(Asset.name == "ghost.webp")
        asset = await db_session.scalar(stmt)
        assert asset is None, "Ghost asset found in DB despite storage failure"

    async def test_no_ghost_asset_on_unexpected_storage_exception(self, real_service, sample_project, db_session):
        """GIVEN presigned_put raises an unexpected exception
        WHEN request_upload_ticket is called
        THEN no Asset row exists in the database.
        """
        real_service._storage.presigned_put.side_effect = RuntimeError("Unexpected crash")

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await real_service.request_upload_ticket(
                project_id=sample_project.id,
                asset_name="crash.webp",
                session_id="session-abc",
            )

        stmt = select(Asset).where(Asset.name == "crash.webp")
        asset = await db_session.scalar(stmt)
        assert asset is None, "Ghost asset found in DB despite unexpected exception"

    async def test_ticket_creates_asset_on_success(self, real_service, sample_project, db_session):
        """GIVEN presigned_put succeeds
        WHEN request_upload_ticket is called
        THEN exactly one Asset row exists.
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="happy.webp",
            session_id="session-abc",
        )

        stmt = select(Asset).where(Asset.id == ticket["asset_id"])
        asset = await db_session.scalar(stmt)
        assert asset is not None
        assert asset.name == "happy.webp"


# ==============================================================================
# Fix 4: Structured Error Handling — custom exception classes
# ==============================================================================


class TestCustomExceptions:
    """Service MUST raise typed exceptions, not stringly-typed ValueErrors."""

    async def test_project_not_found(self, real_service):
        """GIVEN a non-existent project_id
        WHEN request_upload_ticket is called
        THEN ProjectNotFoundError is raised.
        """
        with pytest.raises(ProjectNotFoundError):
            await real_service.request_upload_ticket(
                project_id=str(uuid4()),
                asset_name="test.webp",
                session_id="session-abc",
            )

    async def test_project_ownership_error(self, real_service, sample_project):
        """GIVEN a project owned by a different session
        WHEN request_upload_ticket is called with mismatched session
        THEN ProjectOwnershipError is raised.
        """
        with pytest.raises(ProjectOwnershipError):
            await real_service.request_upload_ticket(
                project_id=sample_project.id,
                asset_name="test.webp",
                session_id="session-wrong",
            )

    async def test_asset_not_found(self, real_service):
        """GIVEN a non-existent asset_id
        WHEN finalize_asset is called
        THEN AssetNotFoundError is raised.
        """
        with pytest.raises(AssetNotFoundError):
            await real_service.finalize_asset(
                asset_id=str(uuid4()),
                session_id="session-abc",
            )

    async def test_storage_not_configured(self, real_service_no_storage):
        """GIVEN no R2Storage backend
        WHEN request_upload_ticket is called
        THEN StorageNotConfiguredError is raised.
        """
        with pytest.raises(StorageNotConfiguredError):
            await real_service_no_storage.request_upload_ticket(
                project_id=str(uuid4()),
                asset_name="test.webp",
                session_id="session-abc",
            )

    async def test_asset_not_found_on_soft_delete(self, real_service):
        """GIVEN a non-existent asset_id
        WHEN soft_delete_asset is called
        THEN AssetNotFoundError is raised.
        """
        with pytest.raises(AssetNotFoundError):
            await real_service.soft_delete_asset(
                asset_id=str(uuid4()),
                session_id="session-abc",
            )

    async def test_project_not_found_on_create_project(self, real_service):
        """GIVEN create_project with empty name
        THEN ValueError is raised (validation, not domain error).
        """
        with pytest.raises(ValueError, match="name and session_id are required"):
            await real_service.create_project(
                name="",
                session_id="session-abc",
            )

    async def test_storage_operation_error_on_storage_failure(self, real_service, sample_project):
        """GIVEN presigned_put fails with StorageError
        WHEN request_upload_ticket is called
        THEN StorageOperationError is raised.
        """
        real_service._storage.presigned_put.side_effect = StorageError("R2 is down")

        with pytest.raises(StorageOperationError):
            await real_service.request_upload_ticket(
                project_id=sample_project.id,
                asset_name="fail.webp",
                session_id="session-abc",
            )


# ==============================================================================
# Fix (PR 4 — 4R): get_active_asset — ownership-validated asset lookup
# ==============================================================================


class TestGetActiveAsset:
    """``get_active_asset`` must validate ownership and return asset data."""

    async def test_returns_asset_dict_for_owned_asset(self, real_service, sample_project, db_session):
        """GIVEN an asset owned by the caller's session
        WHEN get_active_asset is called
        THEN the asset dict is returned with r2_key.
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="active.webp",
            session_id="session-abc",
        )

        result = await real_service.get_active_asset(
            asset_id=ticket["asset_id"],
            session_id="session-abc",
        )

        assert isinstance(result, dict)
        assert result["id"] == ticket["asset_id"]
        assert result["name"] == "active.webp"
        assert "r2_key" in result

    async def test_rejects_unknown_asset(self, real_service):
        """GIVEN a non-existent asset_id
        WHEN get_active_asset is called
        THEN AssetNotFoundError is raised.
        """
        with pytest.raises(AssetNotFoundError):
            await real_service.get_active_asset(
                asset_id=str(uuid4()),
                session_id="session-abc",
            )

    async def test_rejects_ownership_mismatch(self, real_service, sample_project):
        """GIVEN an asset owned by a different session
        WHEN get_active_asset is called with mismatched session
        THEN ProjectOwnershipError is raised.
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="mismatch.webp",
            session_id="session-abc",
        )

        with pytest.raises(ProjectOwnershipError):
            await real_service.get_active_asset(
                asset_id=ticket["asset_id"],
                session_id="session-wrong",
            )

    async def test_rejects_soft_deleted_asset(self, real_service, sample_project):
        """GIVEN an asset that has been soft-deleted
        WHEN get_active_asset is called
        THEN AssetNotFoundError is raised (soft-deleted is not active).
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="deleted.webp",
            session_id="session-abc",
        )

        # Soft-delete it
        await real_service.soft_delete_asset(
            asset_id=ticket["asset_id"],
            session_id="session-abc",
        )

        # Now it should not be found
        with pytest.raises(AssetNotFoundError):
            await real_service.get_active_asset(
                asset_id=ticket["asset_id"],
                session_id="session-abc",
            )

    async def test_returns_asset_with_r2_key(self, real_service, sample_project, db_session):
        """GIVEN an active asset
        WHEN get_active_asset is called
        THEN the returned dict includes the r2_key for URL generation.
        """
        from sqlalchemy import select
        from src.shared.models.persistence import Asset

        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="keycheck.webp",
            session_id="session-abc",
        )

        # Get the stored r2_key from DB
        stmt = select(Asset).where(Asset.id == ticket["asset_id"])
        asset = await db_session.scalar(stmt)

        result = await real_service.get_active_asset(
            asset_id=ticket["asset_id"],
            session_id="session-abc",
        )

        assert result["r2_key"] == asset.r2_key


# ==============================================================================
# Fix 3 (4R): Storage Leak — mark_deleted called on soft delete
# ==============================================================================


class TestSoftDeleteStorageCleanup:
    """``soft_delete_asset`` MUST move the backing R2 object to deleted/."""

    async def test_soft_delete_calls_mark_deleted_with_r2_key(
        self, real_service, sample_project, db_session
    ):
        """GIVEN an existing asset owned by the caller
        WHEN soft_delete_asset is called
        THEN _storage.mark_deleted is called with the asset's r2_key.
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="cleanup.webp",
            session_id="session-abc",
        )

        # Get the stored r2_key
        stmt = select(Asset).where(Asset.id == ticket["asset_id"])
        asset = await db_session.scalar(stmt)

        await real_service.soft_delete_asset(
            asset_id=ticket["asset_id"],
            session_id="session-abc",
        )

        real_service._storage.mark_deleted.assert_awaited_once_with(asset.r2_key)

    async def test_soft_delete_raises_storage_not_configured_without_storage(
        self, real_service_no_storage
    ):
        """GIVEN an AssetsService without R2Storage configured
        WHEN soft_delete_asset is called
        THEN StorageNotConfiguredError is raised.
        """
        with pytest.raises(StorageNotConfiguredError):
            await real_service_no_storage.soft_delete_asset(
                asset_id="any-id",
                session_id="session-abc",
            )

    async def test_soft_delete_raises_storage_operation_error_on_storage_failure(
        self, real_service, sample_project, db_session
    ):
        """GIVEN mark_deleted raises StorageError
        WHEN soft_delete_asset is called
        THEN StorageOperationError is raised.
        """
        ticket = await real_service.request_upload_ticket(
            project_id=sample_project.id,
            asset_name="storagefail.webp",
            session_id="session-abc",
        )

        # Make mark_deleted fail
        real_service._storage.mark_deleted.side_effect = StorageError("R2 is down")

        with pytest.raises(StorageOperationError, match="R2 is down"):
            await real_service.soft_delete_asset(
                asset_id=ticket["asset_id"],
                session_id="session-abc",
            )
