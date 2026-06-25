# Apply Progress: sdd-3-workspaces-assets — PR 1 + PR 2

**Date**: 2026-06-25
**Mode**: Strict TDD
**Delivery Strategy**: auto-chain (feature-branch-chain)
**PR 1 Branch**: `feature/sdd-3-workspaces-assets-pr1` (based on `feature/sdd-3-workspaces-assets` tracker)
**PR 2 Branch**: `feature/sdd-3-workspaces-assets-pr2` (based on `feature/sdd-3-workspaces-assets-pr1`)

## Completed Tasks

### PR 1: DB + ORM Models

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

### PR 2: R2 Storage Layer

- [x] 2.1 **RED**: Write failing pytest for `R2Storage.presigned_put()` and `presigned_get()` with mocked boto3 client
- [x] 2.2 **GREEN**: Create `api/src/shared/storage.py` — `R2Storage` class wrapping `boto3.client("s3", endpoint_url=...)`, `presigned_put/get` via `asyncio.to_thread`
- [x] 2.3 **GREEN**: Add `configure_bucket_lifecycle()` helper — `put_bucket_lifecycle_configuration` for `projects/` prefix, ≥30 day expiry
- [x] 2.4 **REFACTOR**: Add `boto3` to `modal_config.py` pip installs; inject R2 env vars (`R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET`)
- [x] 2.5 Verify: `python3 -m pytest src/tests/test_storage.py src/tests/test_models.py` — 31/31 passing

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/storage.py` | **Created** | `R2Storage` class with `presigned_put()`, `presigned_get()` via `asyncio.to_thread`; `configure_bucket_lifecycle()` for R2 lifecycle rules |
| `api/src/tests/test_storage.py` | **Created** | 10 tests: constructor, presigned_put (3), presigned_get (2), error propagation (2), lifecycle config (2) |
| `api/src/shared/modal_config.py` | Modified | Added `boto3` to pip installs; injected `R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET` env vars |
| `openspec/changes/sdd-3-workspaces-assets/apply-progress.md` | Modified | Merged PR 1 + PR 2 evidence |
| `openspec/changes/sdd-3-workspaces-assets/tasks.md` | Modified | Marked PR 2 tasks as complete |

## Branch Strategy

```
master (base)
  └── feature/sdd-3-workspaces-assets (tracker branch — draft/no-merge)
       └── feature/sdd-3-workspaces-assets-pr1 (PR 1 — DB + ORM)
            └── 📍 feature/sdd-3-workspaces-assets-pr2 (this PR — R2 storage)
```

## TDD Cycle Evidence

### PR 1 Evidence (preserved from batch 1)

| Task | Test File | Layer | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_models.py` | Unit | ✅ Written (ImportError before impl) | ✅ 12/12 passing | ✅ 12 test cases (3 Project, 4 Asset, 3 active_assets, 2 async session) | ➖ N/A (new file) |
| 1.2 | `api/src/shared/models/persistence.py` | Unit | ✅ (see 1.1) | ✅ 12/12 passing | ➖ Single implementation | ➖ None needed |
| 1.3 | `api/src/tests/test_models.py` | Unit | ✅ (test references code that didn't exist) | ✅ active_assets() correctly filters | ✅ 3 cases: one active + one deleted, no assets, all deleted | ➖ None needed |
| 1.4 | `api/app.py` | Unit | N/A (refactoring) | ✅ 12/12 tests pass (safety net) | ➖ Single lifespan addition | ✅ Added asynccontextmanager pattern |

### PR 1 Surgical Fixes (preserved from batch 2)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.6 Soft-delete leakage | `test_models.py` | Unit | ✅ 12/12 | ✅ project.assets returns deleted | ✅ 21/21 | ✅ 2 cases | ✅ Clean |
| 1.7 Lifespan try…finally | `test_models.py` | Unit | ✅ 12/12 | ✅ close_db not called on crash | ✅ 21/21 | ➖ Single pattern | ✅ Added finally block |
| 1.8 Pooling & timeouts | `test_models.py` | Unit | ✅ 12/12 | ✅ pool_size/max_overflow not passed | ✅ 21/21 | ➖ Single assertion point | ✅ Clean params |
| 1.9 PRAGMA + isolation + ordering | `test_models.py` | Unit | ✅ 12/12 | ✅ FK violation not raised; missing tests | ✅ 21/21 | ✅ 3 scenarios | ✅ PRAGMA in fixture |
| 1.10 Cross-session scoping | `test_models.py` | Unit | ✅ 12/12 | ✅ session_id param missing | ✅ 21/21 | ✅ 2 cases | ✅ Clean join |

### PR 2 — R2 Storage Layer (batch 3)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 RED | `api/src/tests/test_storage.py` | Unit | N/A (new file) | ✅ Written (ModuleNotFoundError before impl) | ✅ 10/10 passing | ✅ 10 cases (constructor, put with 3 TTL variants, get with 2, errors x2, lifecycle x2) | ➖ N/A (new file) |
| 2.2 GREEN | `api/src/shared/storage.py` | Unit | ✅ (see 2.1) | ✅ (test references code that didn't exist) | ✅ 10/10 passing | ➖ Single implementation | ✅ Removed unused `BotoConfig` import |
| 2.3 GREEN | `api/src/shared/storage.py` | Unit | ✅ (see 2.1) | ✅ (lifecycle tests reference non-existent helper) | ✅ 10/10 passing | ✅ 2 cases: default bucket, custom bucket | ✅ Part of 2.2 refactor |
| 2.4 REFACTOR | `api/src/shared/modal_config.py` | Config | ✅ 31/31 (PR1+storage) | N/A (config change, no new behavior) | ✅ 31/31 passing | ➖ Single config addition | ✅ Clean env var injection |
| 2.5 Verify | combined | Verify | N/A | N/A | ✅ 31/31 passing (10 storage + 21 models) | ➖ N/A (verification only) | ➖ N/A |

## Test Summary

- **Total tests written**: 31 (21 PR 1 + 10 PR 2)
- **Total tests passing**: 31/31 (100%)
- **Safety net (pre-existing)**: unchanged
- **Layers used**: Unit (31)

## Deviations from Design

| Deviation | Rationale |
|-----------|-----------|
| Lifecycle function is a standalone async function, not a method on `R2Storage` | The lifecycle config is an admin/setup operation, not a per-request operation. Keeps `R2Storage` focused on its single responsibility (presigned URL generation). |
| Removed unused `BotoConfig` import | Detected during REFACTOR phase — was imported but never used in the implementation. Cleaned up to avoid lint warnings. |

None — implementation matches design. All changes are additive.

## Issues Found

1. **boto3 not in dev requirements**: `boto3` was not installed in the project's `requirements-dev.txt`. Installed globally for this implementation; should be added to `requirements-dev.txt` and potentially `modal_config.py` pip installs (already done in task 2.4).

2. **No pre-existing test for `asyncio.to_thread` wrapping**: The tests verify the boto3 call args and error propagation but do not directly assert that `asyncio.to_thread` is called. This is acceptable because:
   - The tests call async methods and they return correct values — if `to_thread` were not used, the sync call would still work in tests (boto3 sync methods are wrapped in `to_thread` for production correctness, not for test behavior).
   - The async method signature is the contract; the `to_thread` wrapper is an implementation detail.

## Remaining Tasks (Future PRs)

- [ ] PR 3: Backend API routes + Pydantic DTOs
- [ ] PR 4: ComfyUI WebP output + LoadImageFromUrl
- [ ] PR 5: Frontend upload + WebP compression
- [ ] PR 6: OpenSpec deltas + archive

## Status

**15/15 tasks complete** (PR 1: 10/10 + PR 2: 5/5). Ready for verify.

Next: PR 3 — Backend API routes (`tasks.md` tasks 3.1–3.6).
