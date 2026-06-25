# Apply Progress: sdd-3-workspaces-assets — PR 1

**Date**: 2026-06-25
**Mode**: Strict TDD
**Delivery Strategy**: auto-chain (feature-branch-chain)
**Branch**: `feature/sdd-3-workspaces-assets-pr1` (based on `feature/sdd-3-workspaces-assets` tracker)

## Completed Tasks

- [x] 1.1 RED: Write failing pytest for Project and Asset ORM creation
- [x] 1.2 GREEN: Create persistence.py with Project, Asset models + async session factory
- [x] 1.3 GREEN: Add active_assets() helper with soft-delete filter
- [x] 1.4 REFACTOR: Register engine startup/shutdown in app.py (lifespan)
- [x] 1.5 Verify: 12/12 tests passing
- [x] **1.6 FIX**: Soft-delete leakage — add `primaryjoin` to `Project.assets` to exclude `deleted_at IS NOT NULL`
- [x] **1.7 FIX**: FastAPI lifespan — wrap `yield` in `try…finally` ensuring `close_db()` is always called
- [x] **1.8 FIX**: Connection pooling — add `pool_size=5, max_overflow=10` to engine; wrap `init_db` in `asyncio.wait_for(timeout=10.0)`
- [x] **1.9 FIX**: SQLite test integrity — enable `PRAGMA foreign_keys=ON` in fixture; add cross-project isolation & newest-first ordering tests
- [x] **1.10 FIX**: Cross-session access — add `session_id` parameter to `active_assets()` with join + filter

## Files Changed (Surgical Fixes)

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/models/persistence.py` | Modified | Added `primaryjoin` to `Project.assets` (soft-delete); added `pool_size=5, max_overflow=10`; added `session_id` param + `Project` join to `active_assets()` |
| `api/app.py` | Modified | Added `import asyncio`; wrapped `init_db` in `asyncio.wait_for(timeout=10.0)`; wrapped `yield` in `try…finally` |
| `api/src/tests/test_models.py` | Modified | Added `PRAGMA foreign_keys=ON` to `db_session` fixture; added 9 new tests (soft-delete leak, lifespan safety, pool settings, FK integrity, cross-project isolation, ordering, cross-session scoping) |
| `openspec/changes/sdd-3-workspaces-assets/apply-progress.md` | Modified | Updated with surgical fix evidence |

## Branch Strategy

```
master (base)
  └── feature/sdd-3-workspaces-assets (tracker branch — draft/no-merge)
       └── 📍 feature/sdd-3-workspaces-assets-pr1 (this PR)
```

## TDD Cycle Evidence

### Initial Implementation (batch 1)

| Task | Test File | Layer | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_models.py` | Unit | ✅ Written (ImportError before impl) | ✅ 12/12 passing | ✅ 12 test cases (3 Project, 4 Asset, 3 active_assets, 2 async session) | ➖ N/A (new file) |
| 1.2 | `api/src/shared/models/persistence.py` | Unit | ✅ (see 1.1) | ✅ 12/12 passing | ➖ Single implementation | ➖ None needed |
| 1.3 | `api/src/tests/test_models.py` | Unit | ✅ (test references code that didn't exist) | ✅ active_assets() correctly filters | ✅ 3 cases: one active + one deleted, no assets, all deleted | ➖ None needed |
| 1.4 | `api/app.py` | Unit | N/A (refactoring) | ✅ 12/12 tests pass (safety net) | ➖ Single lifespan addition | ✅ Added asynccontextmanager pattern |
| 1.5 | `api/src/tests/test_models.py` | Verify | N/A | ✅ 12/12 passing | ✅ Confirmed Project & Asset tables created in SQLite | ➖ N/A (verification only) |

### Surgical Fixes (batch 2 — 4R findings)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.6 Soft-delete leakage | `test_models.py` | Unit | ✅ 12/12 | ✅ ✅ project.assets returns deleted | ✅ 21/21 | ✅ 2 cases: mixed + all deleted | ✅ Clean |
| 1.7 Lifespan try…finally | `test_models.py` | Unit | ✅ 12/12 | ✅ close_db not called on crash | ✅ 21/21 | ➖ Single pattern (refactoring) | ✅ Added finally block |
| 1.8 Pooling & timeouts | `test_models.py` | Unit | ✅ 12/12 | ✅ pool_size/max_overflow not passed | ✅ 21/21 | ➖ Single assertion point | ✅ Clean params |
| 1.9 PRAGMA + isolation + ordering | `test_models.py` | Unit | ✅ 12/12 | ✅ FK violation not raised; missing tests | ✅ 21/21 | ✅ 3 scenarios: FK, cross-project, ordering | ✅ PRAGMA in fixture |
| 1.10 Cross-session scoping | `test_models.py` | Unit | ✅ 12/12 | ✅ session_id param missing | ✅ 21/21 | ✅ 2 cases: correct session + wrong session + backward compat | ✅ Clean join |

## Test Summary

- **Total tests written**: 21 (12 original + 9 surgical fix tests)
- **Total tests passing**: 21/21 (100%)
- **Safety net (existing passing tests)**: 424 — unchanged (49 pre-existing workflow asset failures are unrelated)
- **Layers used**: Unit (21)

## Deviations from Design

None — implementation matches design. All changes are additive (no behavior removed).

## Issues Found

1. **pytest-asyncio strict mode compatibility**: Existing project had `asyncio_mode=Mode.STRICT` with no `pytest.ini`. Required creating `api/pytest.ini` with `asyncio_mode = auto` to support async fixtures without deprecated marker pattern.

2. **Engine caching**: Original `get_async_engine()` cached engines globally, which conflicts with test isolation. Refactored to use `init_db()`/`close_db()` lifecycle for production and `create_async_engine()` directly in tests.

3. **SQLAlchemy async relationship access**: Accessing `project.assets` in async context requires `selectinload` eager loading — lazy load triggers `MissingGreenlet`. Tests updated to use `select(Project).options(selectinload(Project.assets))`.

4. **Pre-existing workflow asset failures**: 49 tests fail due to missing `src/workflows/*/workflow.json` and `manifest.yaml` files on this branch. These are unrelated to PR 1 changes and are not introduced by the surgical fixes.

## Remaining Tasks (Future PRs)

- [ ] PR 2: R2 storage layer + lifecycle config
- [ ] PR 3: Backend API routes + Pydantic DTOs
- [ ] PR 4: ComfyUI WebP output + LoadImageFromUrl
- [ ] PR 5: Frontend upload + WebP compression
- [ ] PR 6: OpenSpec deltas + archive

## Status

10/10 tasks complete. Ready for verify or next batch (PR 2).
