# Apply Progress: sdd-3-workspaces-assets — PR 1

**Date**: 2026-06-24
**Mode**: Strict TDD
**Delivery Strategy**: auto-chain (feature-branch-chain)
**Branch**: `feature/sdd-3-workspaces-assets-pr1` (based on `feature/sdd-3-workspaces-assets` tracker)

## Completed Tasks

- [x] 1.1 RED: Write failing pytest for Project and Asset ORM creation
- [x] 1.2 GREEN: Create persistence.py with Project, Asset models + async session factory
- [x] 1.3 GREEN: Add active_assets() helper with soft-delete filter
- [x] 1.4 REFACTOR: Register engine startup/shutdown in app.py (lifespan)
- [x] 1.5 Verify: 12/12 tests passing

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `api/pytest.ini` | Created | Set `asyncio_mode = auto` for pytest-asyncio compat |
| `api/src/shared/models/__init__.py` | Created | Package init for models module |
| `api/src/shared/models/persistence.py` | Created | Project, Asset ORM models, init_db/close_db lifecycle, async_session_factory, active_assets() helper |
| `api/src/tests/test_models.py` | Created | 12 tests: Project/Asset creation, soft-delete, active_assets filter, async session factory |
| `api/app.py` | Modified | Added FastAPI lifespan context manager (init_db on start, close_db on shutdown) + import |
| `openspec/changes/sdd-3-workspaces-assets/tasks.md` | Modified | Marked PR 1 tasks 1.1–1.5 as complete |

## Branch Strategy

```
master (base)
  └── feature/sdd-3-workspaces-assets (tracker branch — draft/no-merge)
       └── 📍 feature/sdd-3-workspaces-assets-pr1 (this PR)
```

## TDD Cycle Evidence

| Task | Test File | Layer | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_models.py` | Unit | ✅ Written (ImportError before impl) | ✅ 12/12 passing | ✅ 12 test cases (3 Project, 4 Asset, 3 active_assets, 2 async session) | ➖ N/A (new file) |
| 1.2 | `api/src/shared/models/persistence.py` | Unit | ✅ (see 1.1) | ✅ 12/12 passing | ➖ Single implementation | ➖ None needed |
| 1.3 | `api/src/tests/test_models.py` | Unit | ✅ (test references code that didn't exist) | ✅ active_assets() correctly filters | ✅ 3 cases: one active + one deleted, no assets, all deleted | ➖ None needed |
| 1.4 | `api/app.py` | Unit | N/A (refactoring) | ✅ 12/12 tests pass (safety net) | ➖ Single lifespan addition | ✅ Added asynccontextmanager pattern |
| 1.5 | `api/src/tests/test_models.py` | Verify | N/A | ✅ 12/12 passing | ✅ Confirmed Project & Asset tables created in SQLite | ➖ N/A (verification only) |

## Test Summary

- **Total tests written**: 12
- **Total tests passing**: 12
- **Safety net (existing passing tests)**: 415 — unchanged

## Deviations from Design

None — implementation matches design.

## Issues Found

1. **pytest-asyncio strict mode compatibility**: Existing project had `asyncio_mode=Mode.STRICT` with no `pytest.ini`. Required creating `api/pytest.ini` with `asyncio_mode = auto` to support async fixtures without deprecated marker pattern.

2. **Engine caching**: Original `get_async_engine()` cached engines globally, which conflicts with test isolation. Refactored to use `init_db()`/`close_db()` lifecycle for production and `create_async_engine()` directly in tests.

## Remaining Tasks (Future PRs)

- [ ] PR 2: R2 storage layer + lifecycle config
- [ ] PR 3: Backend API routes + Pydantic DTOs
- [ ] PR 4: ComfyUI WebP output + LoadImageFromUrl
- [ ] PR 5: Frontend upload + WebP compression
- [ ] PR 6: OpenSpec deltas + archive

## Status

5/5 tasks complete. Ready for next batch (PR 2) or verify.
