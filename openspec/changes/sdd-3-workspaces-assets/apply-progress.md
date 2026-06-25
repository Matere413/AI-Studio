# Apply Progress: sdd-3-workspaces-assets — PR 1 + PR 2 + PR 3 + PR 4

**Date**: 2026-06-25
**Mode**: Strict TDD
**Delivery Strategy**: auto-chain (feature-branch-chain)
**PR 1 Branch**: `feature/sdd-3-workspaces-assets-pr1` (based on `feature/sdd-3-workspaces-assets` tracker)
**PR 2 Branch**: `feature/sdd-3-workspaces-assets-pr2` (based on `feature/sdd-3-workspaces-assets-pr1`)
**PR 3 Branch**: `feature/sdd-3-workspaces-assets-pr3` (based on `feature/sdd-3-workspaces-assets-pr2`)
**PR 4 Branch**: `feature/sdd-3-workspaces-assets-pr4` (based on `feature/sdd-3-workspaces-assets-pr3`)

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
- [x] **2.6 FIX** (4R): Data Loss — lifecycle prefix `projects/` → `deleted/`; add `expiry_days >= 30` validation
- [x] **2.7 FIX** (4R): Secrets — `modal_config.py` `os.environ` R2 vars → `modal.Secret.from_name("r2-secret")`
- [x] **2.8 FIX** (4R): Resilience — `botocore.config.Config(connect_timeout=5, read_timeout=10, retries={'max_attempts': 3})` in both `boto3.client()` calls
- [x] **2.9 FIX** (4R): Error handling — catch `ClientError`/`BotoCoreError`, raise `StorageError`; update tests to use `botocore` exceptions

### PR 3: Backend API Routes

- [x] 3.1 **RED**: Write failing integration tests for all 4 endpoints (`test_assets_api.py`)
- [x] 3.2 **GREEN**: Create `api/src/features/assets/models.py` — Pydantic v2 schemas: `ProjectCreate`, `AssetResponse`, `ProjectResponse`, `UploadTicketRequest`, `UploadTicketResponse`
- [x] 3.3 **GREEN**: Create `api/src/features/assets/service.py` — `AssetsService` class with `create_project`, `list_projects`, `request_upload_ticket`, `finalize_asset`, `soft_delete_asset`
- [x] 3.4 **GREEN**: Create `api/src/features/assets/router.py` — FastAPI router with 5 endpoints: `POST /projects`, `GET /projects`, `POST /projects/{id}/upload-ticket`, `PATCH /assets/{id}/finalize`, `DELETE /assets/{id}`
- [x] 3.5 **REFACTOR**: Register `assets_router` in `api/app.py`; add `_init_assets_service()` with lazy R2Storage; lifespan integration
- [x] 3.6 Verify: 22/22 integration tests passing + safety net (existing 52 generation router tests + 21 model tests + 19 storage tests)

### PR 4: ComfyUI Adapter + WebP Output

- [x] 4.1 **RED**: Write failing pytest for `_validate_artifact_ownership` accepting `asset_id` owned by caller, rejecting other sessions
- [x] 4.2 **GREEN**: Add `asset_id: Optional[str]` to `ImageArtifact` in `base.py`; add ownership / URL resolution in `dispatch_flow`
- [x] 4.3 **GREEN**: ComfyUI output save as WebP@90% via Pillow (`save(format='webp', quality=90)`)
- [x] 4.4 **GREEN**: Inject `LoadImageFromUrl` custom node; `dispatch_flow` resolves `asset_id` → presigned GET URL → `LoadImageFromUrl`
- [x] 4.5 **REFACTOR**: Accept `image/webp` as valid media type in flow validation
- [x] 4.6 Verify: `python3 -m pytest src/tests/` — 545 passing (8 new tests, baseline 537)

## Files Changed (PR 4)

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/flows/base.py` | **Modified** | Added `asset_id` to `ImageArtifact`; accept `image/webp` in media types |
| `api/src/shared/modal_config.py` | **Modified** | Added `LoadImageFromUrl` custom node alongside `LoadImageFromBase64` |
| `api/src/features/generation/modal_tasks.py` | **Modified** | Convert ComfyUI output to WebP@90% via Pillow; update artifact media_type |
| `api/src/features/generation/service.py` | **Modified** | Added `resolve_asset_url` callback param to `dispatch_flow`; graph patching (LoadImage→LoadImageFromUrl) |
| `api/src/tests/test_ownership.py` | **Created** | 7 unit tests for `asset_id` field acceptance, session ownership validation |
| `api/src/tests/test_flow_base.py` | **Modified** | Added `test_webp_media_type_accepted`; removed `image/webp` from invalid list |
| `api/src/tests/test_modal_config.py` | **Modified** | Added `test_load_image_from_url_node_is_defined` |
| `api/src/tests/test_extraction_flow.py` | **Modified** | Updated `test_invalid_source_media_type_rejected` → `test_webp_source_media_type_accepted` |
| `api/src/tests/test_identity_flow.py` | **Modified** | Updated `test_invalid_source_media_type_rejected` → `test_webp_source_media_type_accepted` |
| `openspec/changes/sdd-3-workspaces-assets/tasks.md` | **Modified** | Marked PR 4 tasks 4.1–4.6 as complete |

## Branch Strategy

```
master (base)
  └── feature/sdd-3-workspaces-assets (tracker branch — draft/no-merge)
       └── feature/sdd-3-workspaces-assets-pr1 (PR 1 — DB + ORM)
            └── feature/sdd-3-workspaces-assets-pr2 (PR 2 — R2 storage)
                 └── feature/sdd-3-workspaces-assets-pr3 (PR 3 — Backend API)
                      └── 📍 feature/sdd-3-workspaces-assets-pr4 (this PR — ComfyUI adapter)
```

## TDD Cycle Evidence

### PR 4 — ComfyUI Adapter + WebP Output (this batch)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1 RED | `test_ownership.py` | Unit | N/A (new file) | ✅ Written (7 tests, AssetError before impl) | ✅ 7/7 | ✅ 4 field + 3 ownership cases | ➖ N/A (test file) |
| 4.2 GREEN | `src/shared/flows/base.py` | Model | ✅ 537/537 | ✅ (asset_id field not found) | ✅ 545/545 | ✅ asset_id + source_job_id + session_id combos | ✅ Clean Pydantic field |
| 4.3 GREEN | `src/features/generation/modal_tasks.py` | Integration | ✅ 537/537 | ✅ (no WebP path in output) | ✅ 545/545 | ✅ WebP fallback on error | ✅ Guarded with try/except |
| 4.4 GREEN | `src/shared/modal_config.py` + `service.py` | Integration + Unit | ✅ 537/537 | ✅ LoadImageFromUrl not present | ✅ 545/545 | ✅ Graph patching + URL resolution | ✅ LoadImageFromUrl alongside Base64 |
| 4.5 REFACTOR | `src/shared/flows/base.py` | Model | ✅ 537/537 | ✅ (webp still in invalid list) | ✅ 545/545 | ✅ webp accepted in extraction + identity flows | ✅ Allowed set + docstring |
| 4.6 Verify | All tests | Verify | N/A | N/A | ✅ 545/545 | ➖ N/A | ➖ N/A |

## Test Summary

- **Total tests written**: 545 (537 baseline + 8 new)
- **Total tests passing**: 545/545 (100%)
- **Safety net (pre-existing)**: 537 ⇒ 545
- **Layers used**: Unit (7 new in test_ownership.py), Model (base.py, extraction, identity), Integration (modal_tasks, modal_config, service)
- **New coverage**: `asset_id` field on ImageArtifact, `image/webp` media type, WebP output conversion, LoadImageFromUrl custom node, asset_id URL resolution in dispatch_flow
- **Pure functions created**: `_convert_to_webp` (inline in modal_tasks), ImageArtifact.asset_id field

## Deviations from Design

| Deviation | Rationale |
|-----------|-----------|
| Asset ownership validation is injected via `resolve_asset_url` callback rather than DB direct | GenerationService has no DB session; callback pattern keeps service testable and decoupled from AssetsService |
| WebP conversion is guarded with try/except | Prevents a failed conversion from breaking the generation pipeline; falls back to original PNG |
| `LoadImageFromUrl` node is in the same `base64_node.py` file as `LoadImageFromBase64` | Simplifies Modal build — one file for both URL-based and base64-based loading; avoids an additional heredoc |

## Issues Found

1. **Pre-existing test failures from wrong CWD**: Tests in `test_composition_flow.py` and `test_extraction_flow.py` that check workflow file existence fail when run from repo root rather than `api/`. This is pre-existing and not addressed here.

2. **image/webp conversion is best-effort**: If Pillow is not available or the file is corrupted, the conversion silently falls back to the original format. In production, missing `Pillow` is impossible (`Pillow` is installed in the Modal image).

3. **LoadImageFromUrl uses `urllib.request` not `requests`**: Keeping dependencies minimal — `urllib` is stdlib. The `requests` library is available in the Modal image but not needed for simple GET.

## Status

**38/38 tasks complete** (PR 1: 10/10 + PR 2: 9/9 + PR 3: 10/10 + 3 surgical + PR 4: 6/6). All 545 tests passing (537 safety net + 8 new).
Current branch: `feature/sdd-3-workspaces-assets-pr4` (based on `feature/sdd-3-workspaces-assets-pr3`).

Next: PR 5 — Frontend Upload + WebP Compression (tasks 5.1–5.7).
