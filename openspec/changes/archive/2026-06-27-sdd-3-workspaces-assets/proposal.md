# Proposal: Workspace Projects & Asset Storage (v2 — Cost-Optimized)

## Intent

Replace browser-only `dataUrl` assets with persistent, Cloudflare R2-backed storage. Introduce Projects for organization (future-proofed via `owner_id`). Minimize storage and egress costs through client-side compression (WebP before upload), server-side output compression (ComfyUI saves WebP instead of PNG), and R2 lifecycle rules for hard-deletion.

## Scope

### In Scope
- DB schema: `Project` and `Asset` ORM (SQLAlchemy 2.0 async)
- **Cloudflare R2** storage layer (boto3-compatible, zero egress fees)
- Frontend **client-side compression**: WebP, max 1024×1024 before requesting presigned URL
- **ComfyUI WebP output**: ~90% quality, replaces PNG (~90% storage reduction)
- REST API: project CRUD, upload tickets, asset finalize, list, soft-delete
- `LoadImageFromUrl` ComfyUI custom node
- Frontend upload state machine with loud error + retry UX
- **R2 lifecycle rules** for hard-deletion of soft-deleted objects (app code only manages `deleted_at`)

### Out of Scope
- Sharing UI / team collaboration
- Trash/recycle-bin UI
- Alembic migrations (deferred to SDD 7+)
- `?include_deleted=true` admin endpoint
- Auto-create default project (users create explicitly)

## Capabilities

### New Capabilities
- `workspace-projects`: Project CRUD, ownership model (`owner_id` nullable), session binding
- `asset-storage`: R2 presigned upload/download, client-side WebP compression gate, asset lifecycle, soft-delete, size enforcement, lifecycle-rule-driven hard purge

### Modified Capabilities
- `api-security`: Ownership check expands from path-based to row-based (`asset_id` > `volume_path`)
- `atomic-flows`: `ImageArtifact` gains `asset_id`; `LoadImageFromUrl` valid input; ComfyUI outputs WebP
- `generative-ai-studio-frontend`: Assets Drawer renders R2-backed assets; upload state machine replaces `dataUrl`; client-side WebP compression before upload

## Approach

Chained PRs (6 slices, each ≤400 lines):

| # | Slice | Deps | ~Lines | Cost-Reduction Impact |
|---|-------|------|--------|----------------------|
| 1 | DB + ORM models | — | 200 | `deleted_at` enables lifecycle purge |
| 2 | R2 storage layer + lifecycle config | — | 200 | Zero egress; lifecycle rules for purge |
| 3 | Backend API routes | 1, 2 | 300 | Presigned URL flow (no proxy bandwidth) |
| 4 | ComfyUI adapter + WebP output | — | 200 | ~90% output storage reduction |
| 5 | Frontend upload + WebP compression | 3 | 300 | ~80% upload size reduction |
| 6 | OpenSpec deltas + archive `view3-ux-polish` | 5 | 200 | — |

Slices 1, 2, 4 can land in parallel. Slice 5 depends on 3 (needs API). Total: ~1400 lines across 6 PRs.

**Cost-reduction pipeline**: User selects file → frontend compresses to WebP ≤1024×1024 → requests presigned PUT → uploads compressed WebP to R2 → ComfyUI generates output as WebP@90% → R2 lifecycle auto-purges soft-deleted objects after N days.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/shared/storage.py` | New | boto3 R2 client (`endpoint_url` = R2), presign helpers, lifecycle config |
| `api/src/shared/db.py` | New | Async SQLAlchemy engine + session factory |
| `api/src/shared/models/persistence.py` | New | `Project`, `Asset` ORM (includes `content_type`, `deleted_at`) |
| `api/src/features/assets/` | New | Router, service, DTOs for projects/assets |
| `api/src/shared/flows/base.py` | Modified | `ImageArtifact.asset_id` field |
| `api/src/shared/modal_config.py` | Modified | R2 env vars, boto3 install |
| `api/src/features/generation/modal_tasks.py` | Modified | ComfyUI output → WebP@90% instead of PNG |
| `view/src/features/assets/` | Modified | Upload state machine, **client-side WebP compression**, R2-backed rendering |
| `view/src/app/studio-state.ts` | Modified | Remove `dataUrl`, add upload status |
| R2 bucket config | New | CORS rules, lifecycle policy (delete after N days on `deleted_at` prefix/tag) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Presigned GET expires before ComfyUI fetch | Med | Re-sign at job-spawn time, 5min TTL |
| R2 CORS misconfiguration | Med | Document required CORS rules; startup health check |
| Client-side WebP compression quality loss | Low | 1024×1024 is sufficient for ComfyUI inputs; quality ≥85% preserves detail |
| Browser WebP support gap (Safari <14) | Low | Canvas `toBlob('image/webp')` has >97% support; fallback to JPEG |
| ComfyUI WebP output compatibility | Low | Pillow `save(format='webp', quality=90)` is standard; verify with all flows |
| Soft-delete filter drift | Low | Single `active_assets()` helper; unit test guard |
| `dataUrl` to R2 migration data loss | Low | Archive `view3-ux-polish` before frontend merge |
| Lifecycle rule deletes before recovery window | Low | Set retention ≥30 days; document in runbook |

## Rollback Plan

Each chained PR is independently revertible. If R2 integration fails post-merge, revert slices 5→3→2 to restore browser-only `dataUrl` path. DB schema (slice 1) is additive and safe to keep. ComfyUI WebP output (slice 4) reverts to PNG independently.

## Dependencies

- `boto3` + Cloudflare R2 bucket with CORS configured for frontend origin
- `sqlalchemy[asyncio]` + `aiosqlite` (dev) / PostgreSQL (prod)
- R2 lifecycle policy configured for soft-delete purge
- `view3-ux-polish` archived before slice 6
- Browser Canvas API for client-side WebP compression (no extra library needed)

## Success Criteria

- [ ] Upload image compressed to WebP ≤1024×1024 client-side, uploaded via presigned PUT to R2
- [ ] Assets persist across browser refreshes
- [ ] ComfyUI generation consumes R2 asset via `LoadImageFromUrl`
- [ ] ComfyUI outputs saved as WebP@90% (not PNG)
- [ ] Soft-deleted assets excluded from all default queries
- [ ] R2 lifecycle rule auto-purges objects with `deleted_at` > 30 days
- [ ] Upload failure shows clear error with retry in UI
- [ ] Zero egress fees confirmed via R2 (no AWS S3 dependency)
