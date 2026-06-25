# Tasks: Workspace Projects & Asset Storage (v2)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1400 (6 slices, each ≤400) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | DB + ORM (Project, Asset, async session) | PR 1 | Base: feature/tracker; independent |
| 2 | R2 storage layer + lifecycle config | PR 2 | Base: PR 1 branch; independent of 1 |
| 3 | Backend API routes + Pydantic DTOs | PR 3 | Base: PR 2 branch; depends on 1+2 |
| 4 | ComfyUI WebP output + LoadImageFromUrl | PR 4 | Base: PR 3 branch; independent |
| 5 | Frontend upload state machine + WebP compression | PR 5 | Base: PR 4 branch; depends on 3 |
| 6 | OpenSpec deltas + archive view3-ux-polish | PR 6 | Base: PR 5 branch; depends on 5 |

## PR 1: DB + ORM Models (~200 lines + surgical fixes)

- [x] 1.1 **RED**: Write failing pytest for `Project` and `Asset` ORM creation with `deleted_at` filter (`api/src/tests/test_models.py`)
- [x] 1.2 **GREEN**: Create `api/src/shared/models/persistence.py` — `Project(id, name, owner_id, session_id)`, `Asset(id, name, content_type, r2_key, project_id, deleted_at, created_at)`, async engine + session factory
- [x] 1.3 **GREEN**: Add `active_assets()` helper that filters `deleted_at IS NULL`; verify test passes
- [x] 1.4 **REFACTOR**: Register engine startup/shutdown in `api/app.py` (lifespan context manager)
- [x] 1.5 Verify: `python3 -m pytest api/src/tests/test_models.py` passes; `Project` and `Asset` tables created in SQLite
- [x] 1.6 **FIX** (4R): Add `primaryjoin` to `Project.assets` relationship excluding `Asset.deleted_at.is_(None)`
- [x] 1.7 **FIX** (4R): Wrap `yield` in `try…finally` in `lifespan`; use `asyncio.wait_for(init_db(), timeout=10.0)`
- [x] 1.8 **FIX** (4R): Add `pool_size=5, max_overflow=10` to `create_async_engine` in `init_db()`
- [x] 1.9 **FIX** (4R): Enable `PRAGMA foreign_keys=ON` in SQLite test fixture; add cross-project isolation & newest-first ordering tests
- [x] 1.10 **FIX** (4R): Add `session_id: str | None` param to `active_assets()` to enforce caller's session boundary

## PR 2: R2 Storage Layer (~200 lines)

- [x] 2.1 **RED**: Write failing pytest for `R2Storage.presigned_put()` and `presigned_get()` with mocked boto3 client (`api/src/tests/test_storage.py`)
- [x] 2.2 **GREEN**: Create `api/src/shared/storage.py` — `R2Storage` class wrapping `boto3.client("s3", endpoint_url=...)`, `presigned_put(key, ttl=300)`, `presigned_get(key, ttl=300)` via `asyncio.to_thread`
- [x] 2.3 **GREEN**: Add R2 lifecycle config helper (`configure_bucket_lifecycle` for `projects/` prefix, ≥30 day expiry)
- [x] 2.4 **REFACTOR**: Add `boto3` to `modal_config.py` pip installs; inject R2 env vars (`R2_ENDPOINT`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET`)
- [x] 2.5 Verify: `python3 -m pytest src/tests/test_storage.py src/tests/test_models.py` passes (31/31 with mocked S3)
- [x] **2.6 FIX** (4R — Data Loss): Lifecycle prefix `projects/` → `deleted/`; add `expiry_days >= 30` `ValueError` validation guard; update test assertions
- [x] **2.7 FIX** (4R — Secrets): `modal_config.py` — remove `os.environ.get("R2_*")` reads; add `r2_secret = modal.Secret.from_name("r2-secret")`; remove R2 vars from `.env()` dict; add `test_r2_secret_defined` in `test_modal_config.py`
- [x] **2.8 FIX** (4R — Resilience): Inject `botocore.config.Config(connect_timeout=5, read_timeout=10, retries={'max_attempts': 3})` into both `boto3.client()` calls in `storage.py`; verify with arg-inspection tests
- [x] **2.9 FIX** (4R — Error handling): Define `StorageError` in `storage.py`; catch `ClientError`/`BotoCoreError` → raise `StorageError` in all S3 API calls; update test fixtures to use `botocore.exceptions.ClientError` instead of generic `Exception`; add `StorageError` lifecycle test

## PR 3: Backend API Routes (~300 lines)

- [x] 3.1 **RED**: Write failing integration tests for `POST /projects`, `POST /projects/{id}/upload-ticket`, `PATCH /assets/{id}/finalize`, `DELETE /assets/{id}` (`api/src/tests/test_assets_api.py`)
- [x] 3.2 **GREEN**: Create `api/src/features/assets/models.py` — Pydantic v2 schemas: `ProjectCreate`, `AssetResponse`, `UploadTicketResponse`
- [x] 3.3 **GREEN**: Create `api/src/features/assets/service.py` — business logic: project CRUD, presigned URL generation, ownership validation, soft-delete
- [x] 3.4 **GREEN**: Create `api/src/features/assets/router.py` — FastAPI router with all 4 endpoints; wire `selectinload(Project.assets)` for list
- [x] 3.5 **REFACTOR**: Register `assets_router` in `api/app.py`; verify integration tests pass with httpx + in-memory SQLite
- [x] 3.6 Verify: full upload flow (ticket → PUT mock → finalize → list → soft-delete)

## PR 4: ComfyUI Adapter + WebP Output (~200 lines)

- [ ] 4.1 **RED**: Write failing pytest for `_validate_artifact_ownership` accepting `asset_id` owned by caller, rejecting other sessions (`api/src/tests/test_ownership.py`)
- [ ] 4.2 **GREEN**: Modify `api/src/shared/flows/base.py` — add `asset_id: Optional[str]` to `ImageArtifact`; add ownership guard using `asset_id` → DB lookup
- [ ] 4.3 **GREEN**: Modify `api/src/features/generation/modal_tasks.py` — ComfyUI output save as WebP@90% via Pillow (`save(format='webp', quality=90)`)
- [ ] 4.4 **GREEN**: Modify `api/src/shared/modal_config.py` — inject `LoadImageFromUrl` custom node into ComfyUI image; resolve `asset_id` to fresh presigned GET at dispatch
- [ ] 4.5 **REFACTOR**: Accept `image/webp` as valid media type in flow validation
- [ ] 4.6 Verify: `python3 -m pytest api/src/tests/test_ownership.py` passes; WebP output confirmed

## PR 5: Frontend Upload + WebP Compression (~300 lines)

- [ ] 5.1 **RED**: Write failing vitest for `studioReducer` — no `dataUrl` field, `uploadStatus` state transitions (`view/src/features/assets/__tests__/reducer.test.ts`)
- [ ] 5.2 **GREEN**: Modify `view/src/app/studio-state.ts` — remove `dataUrl` from `Asset`; add `r2Url`, `uploadStatus: UploadStatus`
- [ ] 5.3 **GREEN**: Create `view/src/features/assets/infrastructure/api.ts` — `requestUploadTicket()`, `finalizeAsset()`, `deleteAsset()` API clients using `fetchWithSession()`
- [ ] 5.4 **GREEN**: Create `view/src/features/assets/application/use-upload.ts` — upload state machine hook: idle→compressing→requesting_ticket→uploading→done|error with retry
- [ ] 5.5 **GREEN**: Modify `view/src/features/assets/presentation/components/AssetsDrawer.tsx` — replace `FileReader`+`dataUrl` with canvas WebP compression (≤1024×1024, quality 0.85) + R2 upload pipeline; add error + retry UX
- [ ] 5.6 **REFACTOR**: Modify `view/src/shared/infrastructure/api-client.ts` — add `fetchWithSession()` helper
- [ ] 5.7 Verify: vitest passes; manual test: 4MB JPEG → WebP ≤1024×1024 → R2 upload → thumbnail renders

## PR 6: OpenSpec Deltas + Archive (~200 lines)

- [ ] 6.1 Archive `view3-ux-polish` change (sync delta specs to baseline)
- [ ] 6.2 Update `openspec/changes/sdd-3-workspaces-assets/` with final verified specs
- [ ] 6.3 Verify: all delta specs match implemented behavior; no orphaned references
