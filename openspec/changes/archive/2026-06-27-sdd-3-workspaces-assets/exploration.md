# Exploration: sdd-3-workspaces-assets

## Goal

Introduce two persistent domain entities (Projects, Assets) backed by an S3/R2
object store, with browser-direct uploads via presigned URLs, soft-delete on
assets, and a fail-honest upload UX. Replaces the current browser-only
`FileReader.readAsDataURL` path (`sessionAssets[].dataUrl`) and the
Modal `input_volume` indirection with an HTTP/REST-friendly contract.

## Confirmed Product Decisions

1. **Projects** — Visual folder for organization today, but the data model
   must be ready to share later. Concretely: include an `owner_id` column
   (nullable, indexed) on `projects` so a future "share with team" feature
   is a migration, not a schema rewrite. No sharing UI is in scope.
2. **Asset deletion** — Soft delete via a `deleted_at` timestamp column on
   the `assets` table. No recycle-bin UI yet. Default queries MUST filter
   `deleted_at IS NULL`; a `?include_deleted=true` admin path is out of
   scope.
3. **Upload mechanism** — Presigned URLs. The browser asks the FastAPI
   backend for an upload ticket (`POST /uploads`), uploads directly to
   S3/R2, then calls `POST /assets` to register metadata. Backend never
   sees the file bytes.
4. **Resilient UX** — Loud, honest failure. If the presign request fails,
   the PUT to S3 fails, or the `POST /assets` finalize fails, the UI
   surfaces a clear error with a retry button. No silent retries, no
   fake "uploading…" forever.

## Current State

### Backend (api/)

- `api/src/features/generation/router.py` — Exposes `POST /generate`,
  `POST /generate/{extraction,composition,identity}`, `GET /images/{job_id}`,
  `WS /ws/generate/{job_id}`. No upload endpoints exist.
- `api/src/features/generation/models.py` — `GenerateRequest`,
  `GenerateResponse`, `JobEvent`. All request shapes are JSON; no file
  ingestion.
- `api/src/features/generation/service.py` — `GenerationService` owns job
  lifecycle. `_validate_artifact_ownership` already enforces that
  `ImageArtifact.volume_path` starting with `input/` must belong to the
  request session (or carry a `source_job_id`). The `input/` namespace
  is the soft contract for "user-uploaded asset" today.
- `api/src/shared/flows/base.py` — `ImageArtifact` carries
  `volume_path`, `media_type`, `source_job_id`, `owner_session_id`,
  `width`, `height`. `volume_path` is the primary handoff path; URL
  ingestion is not yet first-class.
- `api/src/shared/job_store.py` — `JobStore` backed by
  `modal.Dict.from_name("api-blanca-jobs", create_if_missing=True)`.
  Stores ephemeral job state (status, image_path, session_id). No
  persistent domain tables exist.
- `api/src/shared/modal_config.py` — Defines `model_volume`,
  `image_volume`, `input_volume` (all `modal.Volume`). `input_volume` is
  mounted at `/root/ComfyUI/input` and used for chained artifacts
  between flows. The Modal image ships a custom `LoadImageFromBase64`
  node; there is no `LoadImageFromUrl` yet.
- `api/src/features/generation/modal_tasks.py` — `_execute_generation`
  resolves outputs from `/root/ComfyUI/output`. Inputs come from
  `input_volume` via path injection; `image_base64` is decoded by
  `LoadImageFromBase64` in the ComfyUI graph.
- `api/src/tests/` — Pytest suite. `test_generation_models.py`,
  `test_generation_router.py`, `test_generation_service.py`,
  `test_app.py` cover the existing contract. No tests for upload,
  asset, or project endpoints yet.

### Frontend (view/)

- `view/src/features/assets/presentation/components/AssetsDrawer.tsx` —
  Uses `useRef<HTMLInputElement>` + `FileReader.readAsDataURL`. The
  resulting Data URI is dispatched to `ADD_SESSION_ASSET` and stored in
  the reducer (`sessionAssets: Asset[]` with `dataUrl: string`).
- `view/src/features/assets/presentation/components/AssetList.tsx` —
  Renders thumbnails from `dataUrl`. A per-asset `CloseIcon` button
  dispatches `REMOVE_SESSION_ASSET`.
- `view/src/app/studio-state.ts` — Reducer state holds
  `sessionAssets: Asset[]` (browser-only, lost on refresh) and
  `editingReferenceBase64: string | null` (browser-only base64 for
  flux2_editing). `editingReferenceBase64` is the only flow that
  currently sends raw file bytes to the backend.
- `view/src/shared/infrastructure/api-client.ts` — Re-exports
  `submitGenerate`, `getWsUrl`, `fetchImageBinary`, `normalizeError`.
  No upload helper exists. `X-Session-ID` header is injected on every
  request from `localStorage` (key: `ai-studio-session-id`).
- `view/src/features/chat/application/` — `buildGenerateRequest`
  constructs the POST body. `useGenerationJob` opens the WebSocket.

### OpenSpec State

- `openspec/specs/api-security/spec.md` — `Session-Scoped Input Artifact
  Ownership` requires `input/{session_uuid}/...` paths. This rule must
  remain valid: S3-backed assets carry an equivalent `owner_session_id`
  / `project_id` binding, and the ownership check moves from
  path-based to row-based.
- `openspec/specs/atomic-flows/spec.md` — Defines `ImageArtifact` and
  session-owned `input/`. Soft-delete does not change the artifact
  contract, but `volume_path` semantics expand: it can now be an
  S3 key (e.g. `s3://bucket/...`) or the existing relative volume
  path. `LoadImageFromUrl` becomes a valid input source.
- `openspec/specs/generative-ai-studio-frontend/spec.md` — `Assets
  Drawer` requirement currently says "uploads store URL in store".
  In practice the URL is a Data URI. The spec must be updated to
  reflect: uploads store an S3-backed asset reference, not a Data
  URI; thumbnails come from a presigned GET or public CDN URL.
- `openspec/changes/view3-ux-polish/` — Just shipped (PR-equivalent).
  It added the `Asset` type with `dataUrl`. SDD 3 supersedes that
  Data-URI representation with a server-backed asset record.

### Development Plan Alignment

`developmentPlan.md` SDD 3 lists:
- DB schema for `Projects` and `Assets`.
- Direct S3/R2 upload from the frontend.
- Python API payloads consume S3 URLs instead of heavy Base64.

These three bullets are exactly what this change delivers.

## Affected Areas

### Backend (api/)

- `api/src/features/generation/router.py` — Add new routes:
  `POST /projects`, `GET /projects`, `POST /projects/{id}/assets/upload`
  (returns presigned PUT), `POST /assets` (finalize, registers metadata),
  `GET /projects/{id}/assets` (list), `DELETE /assets/{id}` (soft delete).
  All require `X-Session-ID`; `owner_session_id` is derived from the
  header.
- `api/src/features/generation/models.py` — New Pydantic v2 DTOs:
  `ProjectCreate`, `ProjectOut`, `UploadTicketRequest`,
  `UploadTicketResponse`, `AssetCreate`, `AssetOut`, `AssetList`.
- `api/src/features/generation/service.py` — New
  `ProjectService` and `AssetService` classes. Inject the S3 client
  and the DB session. Keep `GenerationService` unchanged; only its
  `_validate_artifact_ownership` needs to learn about
  `source: "s3"` artifacts (cross-service reference by `asset_id`).
- `api/src/shared/storage.py` (new) — S3/R2 client factory.
  `boto3.client("s3", ...)` with explicit `endpoint_url` for R2.
  Functions: `generate_upload_url(key, content_type, expires=900)`,
  `generate_download_url(key, expires=300)`, `head_object(key)`,
  `delete_object(key)`.
- `api/src/shared/db.py` (new) — SQLAlchemy 2.0 async engine +
  `AsyncSession` factory. `DATABASE_URL` env var (default
  `sqlite+aiosqlite:///./ai_studio.db` for local; Postgres in prod).
  `init_db()` runs `metadata.create_all()` for the MVP.
- `api/src/shared/models/persistence.py` (new) — ORM models:
  `Project` (`id`, `name`, `owner_id` nullable, `created_at`,
  `updated_at`) and `Asset` (`id`, `project_id`, `owner_session_id`,
  `s3_key`, `content_type`, `size_bytes`, `width`, `height`,
  `original_filename`, `created_at`, `deleted_at`).
- `api/src/shared/flows/base.py` — `ImageArtifact` gets an optional
  `asset_id: UUID` field. When present, the service resolves it to an
  S3 key + presigned GET URL, then either downloads to local volume
  (for legacy ComfyUI nodes) or inlines the URL into the graph via a
  new `LoadImageFromUrl` node.
- `api/src/features/generation/modal_tasks.py` — Add an
  `input_from_s3(job_id, asset_id)` helper that downloads from S3 to
  `input_volume` once, then mounts at `/root/ComfyUI/input`. This
  keeps ComfyUI's file-based pipeline intact while making the upload
  S3-native. Alternatively, register a `LoadImageFromUrl` custom
  node and let ComfyUI fetch directly.
- `api/src/shared/modal_config.py` — Mount the S3 client config
  (env: `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`,
  `S3_SECRET_ACCESS_KEY`, `S3_REGION`). Add `pip install boto3` to
  `comfyui_run_commands`.
- `api/requirements-dev.txt` — Add `boto3`, `sqlalchemy[asyncio]`,
  `aiosqlite` (dev), `alembic` deferred.
- `api/src/shared/job_store.py` — Unchanged. Job state stays on
  `modal.Dict`. Persistent domain data lives in the new DB.
- `api/app.py` — Lifespan hook for DB init and S3 client warm-up.
  Register new routers. CORS allowlist unchanged.

### Frontend (view/)

- `view/src/features/assets/domain/` — New types:
  `Project`, `ProjectId`, `AssetRecord`, `AssetId`,
  `UploadTicket`, `UploadStatus` (`idle | requesting-ticket |
  uploading | registering | done | error`).
- `view/src/features/assets/infrastructure/` — New API client
  functions: `createProject(name)`, `listProjects()`,
  `requestUploadTicket(projectId, file)`,
  `registerAsset(projectId, s3Key, ticket)`, `listProjectAssets(projectId)`,
  `deleteAsset(assetId)`. All inject `X-Session-ID`.
- `view/src/features/assets/application/` — New hooks:
  `useProjects()`, `useUploadAsset()` (state machine for
  `UploadStatus`), `useAssets(projectId)`. Centralize error
  handling and retry.
- `view/src/features/assets/presentation/components/AssetsDrawer.tsx` —
  Replace `FileReader.readAsDataURL` with the presigned PUT flow.
  Show a per-asset status pill: "Uploading 47%…", "Finalizing…",
  "Failed — Retry". The visible "no-op silent" path is gone.
- `view/src/features/assets/presentation/components/AssetList.tsx` —
  Render thumbnail from a presigned GET URL (returned by
  `GET /projects/{id}/assets`) or the upload response. Per-asset
  retry button when `status === "error"`.
- `view/src/app/studio-state.ts` — Replace `Asset.dataUrl` with
  `Asset.uploadStatus`, `Asset.assetId`, `Asset.previewUrl`,
  `Asset.error`. The reducer gains a
  `SET_ASSET_UPLOAD_STATUS` action. The `dataUrl` field is removed.
- `view/src/app/page.tsx` — Initialize a default project on first
  upload (or surface a project picker). No silent local-only assets.
- `view/src/shared/infrastructure/api-client.ts` — Add `X-Session-ID`
  injection to the new upload helpers; reuse the existing
  `getSessionId()`.
- `view/test/` — New contract tests for the upload state machine
  and retry semantics.

### OpenSpec

- New delta: `openspec/changes/sdd-3-workspaces-assets/specs/projects/spec.md`
  and `specs/assets/spec.md`.
- Modify `openspec/specs/api-security/spec.md` — Replace
  `input/{session_uuid}/...` path-based ownership with
  `owner_session_id` row-based ownership. The path-based rule stays
  as a fallback for the transitional window.
- Modify `openspec/specs/atomic-flows/spec.md` — `ImageArtifact`
  accepts `asset_id` and `s3_url` sources. `LoadImageFromUrl` becomes
  a recognized input path.
- Modify `openspec/specs/generative-ai-studio-frontend/spec.md` —
  `Assets Drawer` no longer renders Data URIs; the source of truth is
  server-backed assets with explicit upload states.
- Archive `view3-ux-polish` before merging the frontend deltas
  (its `Asset.dataUrl` is about to be removed).

## Approaches

### 1. Database persistence

| Option | Description | Pros | Cons | Effort |
|--------|-------------|------|------|--------|
| **A. SQLAlchemy 2.0 async + SQLite (dev) / Postgres (prod)** | New `db.py`, async engine, ORM models for `Project` and `Asset`. SQLite for local + Modal volume; Postgres when prod is real. | Type-safe Pydantic mappers; aligns with python-backend-mastery skill (AsyncSession, `select()`); easy to test; no Modal coupling. | Adds a runtime dep; need a migration story (alembic deferred to SDD 7 or later). | Medium |
| B. `modal.Dict` only | Reuse the existing pattern. New keys for projects/assets. | Zero new infra. | No referential integrity; no real queries; eventual consistency; wrong tool for "the model must be ready to share". | Low (today), High (later) |
| C. S3-only metadata | No DB; project names and asset records live in S3 object metadata. | No new infra. | Unqueryable; multi-user sharing is a rewrite; violates "model must be prepared to share". | High (to reverse) |

**Recommendation: A.** It directly serves the "ready to share" decision and
keeps the boundary between ephemeral job state (modal.Dict) and
persistent domain (DB) clean.

### 2. S3 upload

| Option | Description | Pros | Cons | Effort |
|--------|-------------|------|------|--------|
| **A. Browser-direct presigned PUT** | Backend returns a presigned URL; browser PUTs the file to S3; browser calls `POST /assets` to register. Backend never sees the bytes. | Fast, scalable, minimal API cost; the canonical S3 pattern; matches the "direct from frontend" requirement. | Browser CORS on the bucket must allow PUT from `localhost:3000`; presigned URL expiry must be tight (≤ 15 min). | Medium |
| B. Backend proxy | Browser POSTs the file to FastAPI; FastAPI streams to S3. | Single CORS surface; easier to add virus scan / size enforcement server-side. | Double bandwidth (browser→API→S3); slow for large files; backend can become a bottleneck. | Low |
| C. Multipart from browser | Browser uses S3 multipart for large files. | Best for >100MB files. | Heavy for an MVP; not required for image-only assets (<10MB cap already enforced). | High |

**Recommendation: A.** It matches the explicit "frontend asks the ticket
and uploads direct to S3/R2" decision.

### 3. Soft delete

| Option | Description | Pros | Cons | Effort |
|--------|-------------|------|------|--------|
| **A. `deleted_at` column + default-scope queries** | Every read filters `WHERE deleted_at IS NULL`. A periodic job can hard-delete after N days (out of scope now). | Simple; reversible within the window; matches the decision. | Every query needs the filter — easy to forget. Use a `queryset()` helper on the service to enforce. | Low |
| B. Tombstone table | Separate `asset_deletions(id, asset_id, deleted_at)`. | Keeps the source table clean. | Two-table joins for every read; no upside at this scale. | Medium |
| C. Hard delete | Just `DELETE`. | Simplest. | Violates the explicit product decision. | — |

**Recommendation: A.**

### 4. ComfyUI payload adaptation (S3 → graph)

| Option | Description | Pros | Cons | Effort |
|--------|-------------|------|------|--------|
| **A. Add `LoadImageFromUrl` custom node** | ComfyUI fetches directly from a presigned GET URL. | One-time graph edit; no extra storage; no race condition. | ComfyUI must allow outbound HTTPS to S3 endpoint; presigned GET expires (need to re-sign at job start). | Medium |
| B. Backend downloads S3 → `input_volume` before spawning | Service layer downloads once, places at `/root/ComfyUI/input/{session}/...`, then proceeds. | Reuses existing `input_volume` pattern; ComfyUI stays file-only. | Extra network hop per job; cold-start cost; storage duplicated. | Medium |
| C. Both — short-lived download + URL node | Use URL node for editing flow (small), download for identity/composition (large, GPU-sensitive). | Best of both. | Two code paths to maintain. | High |

**Recommendation: A for MVP**, with a fallback to B for any flow that
needs the file on disk for controlnet preprocessors. Document the
choice in `design.md`.

## Recommendation

Ship a single PR that includes:

1. **Backend storage layer** — `boto3` S3 client with presign helpers
   (`api/src/shared/storage.py`).
2. **Backend persistence layer** — SQLAlchemy 2.0 async + SQLite
   (`api/src/shared/db.py`) + ORM models for `Project` and `Asset`
   (`api/src/shared/models/persistence.py`). Include `owner_id`
   (nullable, indexed) on `Project` and `owner_session_id` on
   `Asset`. `deleted_at` on `Asset`. Default-scope queries.
3. **Backend API** — New routers for projects, upload tickets,
   asset finalize, asset list, and soft delete. Pydantic v2 DTOs.
   `X-Session-ID` drives `owner_session_id`. Mapping: a project
   created without an explicit owner is "session-owned" today
   (logged in the `owner_session_id` column) and ready to migrate
   to `owner_id = user_id` later.
4. **Backend ComfyUI adapter** — New `LoadImageFromUrl` custom node
   in the Modal image. `ImageArtifact.asset_id` resolution path in
   `GenerationService` rewrites the graph to point at a fresh
   presigned GET URL at job-spawn time.
5. **Frontend** — New upload state machine hook
   (`useUploadAsset`), presigned-PUT API client, project picker on
   the assets drawer, loud error UI with retry. `Asset.dataUrl`
   removed; thumbnail is a presigned GET URL.
6. **OpenSpec deltas** — `projects` and `assets` specs (new),
   modifications to `api-security`, `atomic-flows`, and
   `generative-ai-studio-frontend` to align with the new contract.
   Archive `view3-ux-polish` (its `dataUrl` shape is gone).

### Review budget forecast

- Backend: ~500–600 lines (db, models, storage, router, service, tests).
- Frontend: ~300–400 lines (hook, API client, drawer rewrite, tests).
- OpenSpec deltas: ~200 lines.
- **Total: ~1000–1200 lines** — exceeds the 400-line review budget.

**Chained PRs recommended: Yes.**

Suggested slices (each a self-contained, revertible PR):

| # | Slice | Scope | Approx. lines |
|---|-------|-------|---------------|
| 1 | DB + ORM models | `db.py`, `persistence.py`, `Project`/`Asset` model tests | ~200 |
| 2 | S3 storage layer | `storage.py` (boto3 + presign), unit tests with moto | ~200 |
| 3 | Backend API routes | `routers/assets.py`, `routers/projects.py`, DTOs, integration tests | ~300 |
| 4 | ComfyUI adapter | `LoadImageFromUrl` node, `ImageArtifact.asset_id` resolution, `modal_tasks.py` change | ~200 |
| 5 | Frontend upload state machine | `useUploadAsset` hook, API client, error UI | ~300 |
| 6 | OpenSpec deltas + archive view3-ux-polish | new specs, modified specs, archive report | ~200 |

Each slice is independently shippable. Slices 1, 2, and 4 can land in
parallel; slice 3 needs 1 and 2; slice 5 needs 3.

## Risks

- **Race between presign expiry and ComfyUI fetch** — Presigned GET
  URLs have a TTL. The service must re-sign at job-spawn time, not at
  ticket-request time. Mitigation: spawn-time signing in
  `GenerationService.dispatch_flow`; document the 5-minute default TTL.
- **S3 CORS misconfiguration** — Bucket CORS must allow `PUT` from the
  frontend origin with the right headers. Mitigation: document the
  required CORS rules in `design.md`; add a startup health check.
- **Owner semantics during the transition** — `owner_session_id` is
  the only ownership check today. When SDD 4 (LLM Orchestrator) lands
  with real users, the `owner_id` column on `Project` will be
  populated. Code must not hardcode session-only checks. Mitigation:
  every ownership check goes through one helper
  (`assert_can_read_asset`); tests cover both modes.
- **Asset leaking from prior flows** — Existing chained
  `ImageArtifact.volume_path` paths reference `input/...` and
  `output/...` namespaces that pre-date S3. The new
  `ImageArtifact.asset_id` must NOT be confused with the legacy
  path-based ownership rule. Mitigation: `MODIFIED` delta on
  `api-security` makes the precedence explicit:
  `asset_id` ownership > path ownership.
- **Soft-delete queries can drift** — Every read must filter
  `deleted_at IS NULL`. Mitigation: a single `active_assets(...)`
  helper in the asset service; static analysis or a unit test that
  fails if any model method bypasses it.
- **DataURI → S3 migration of existing UX** — `view3-ux-polish`
  just shipped `Asset.dataUrl`. Users may have assets in flight.
  Mitigation: archive `view3-ux-polish` before merging the frontend
  deltas; document the data loss in the change log.
- **Modal `input_volume` now has two sources of truth** — Old code
  writes to `/root/ComfyUI/input/{session}/...`; new code writes to
  S3 and downloads at job time. Mitigation: deprecate
  `input_volume` writes in `modal_tasks.py` after the new flow
  proves itself; do it in a follow-up slice.
- **Review budget** — ~1000–1200 lines crosses the 400-line cap.
  Chained PRs are mandatory, not optional.
- **CORS on the FastAPI side for the new routes** — New
  `POST /uploads` and `POST /assets` will go through the same
  CORS middleware; no change needed, but tests must cover preflight.

## Ready for Proposal

**Yes.** All four product decisions are concrete, the affected
files are mapped, the storage/DB/upload/soft-delete choices are
weighed with a clear recommendation, and the chained-PR forecast is
explicit. The next phase (`sdd-propose`) should produce a proposal
that locks the chained-PR strategy and confirms the slice order
above.

## Open Questions for Proposal

- Should the default project be auto-created on first upload, or
  must the user pick a project explicitly? Recommendation: auto-create
  one "Default Project" per session, with a future "rename / create
  new project" UI in SDD 4 or later.
- Presigned URL TTLs: 15 min for PUT, 5 min for GET. Confirm both.
- Should `Asset.size_bytes` be enforced server-side, or is the
  existing 10MB browser check enough? Recommendation: re-enforce
  server-side via a `head_object` size check at finalize time.
- `LoadImageFromUrl` vs S3-download-to-volume: confirm A for the
  MVP and revisit if a flow needs on-disk access.
