# Design: Workspace Projects & Asset Storage (v2)

## Technical Approach

Persist assets to Cloudflare R2 via presigned URLs with client-side WebP compression gate. Layer an SQLAlchemy 2.0 async model (`Project`, `Asset`) over SQLite/PostgreSQL for ownership tracking and soft-delete lifecycle. Modify ComfyUI to output WebP@90% and consume assets via `LoadImageFromUrl` node. Replace frontend `dataUrl` storage with an upload state machine backed by R2 presigned URLs. Follow existing hexagonal architecture: feature routers/services in `api/src/features/assets/`, R2 client in `api/src/shared/`.

## Architecture Decisions

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| **boto3 with R2 endpoint** vs Cloudflare SDK vs `aioboto3` | boto3 is mature, R2-compatible; `aioboto3` adds complexity for presign-only ops | boto3 (sync `generate_presigned_url`), called via `asyncio.to_thread` |
| **Canvas `toBlob('image/webp')`** vs `browser-image-compression` lib | Canvas is 0-dependency, >97% browser support; lib adds bundle weight and maintenance | Native canvas WebP (quality 0.85), fallback JPEG for Safari<14 |
| **SQLAlchemy `selectinload`** for asset queries | Avoids N+1 when listing project assets; standard async pattern | `selectinload(Project.assets)` in list endpoints |
| **5-min presigned TTL** | Shorter = less exposure; ComfyUI cold-start may need re-sign | 5 min; re-sign at `dispatch_flow` time if needed |
| **DB in `api/src/shared/models/persistence.py`** | Colocates all ORM in a single shared module; avoids feature-isolated models that complicate migrations | Single `persistence.py` for both `Project` and `Asset` |

## Data Flow

```
User selects file
      │
      ▼
Canvas WebP compress (≤1024×1024)
      │
      ▼
POST /api/projects/{id}/upload-ticket
      │
      ▼
Backend: presigned PUT URL (boto3, 5min TTL)
      │
      ▼
fetch PUT → R2 (direct, no proxy)
      │
      ▼
PATCH /api/assets/{id}/finalize (confirm upload)
      │
      ▼
Asset listed in drawer (R2 presigned GET URL)
      │
      ▼
dispatch_flow: asset_id → fresh presigned GET → LoadImageFromUrl node
      │
      ▼
ComfyUI output → WebP@90% → R2
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/models/persistence.py` | **Create** | `Project`, `Asset` ORM with `deleted_at`, `content_type`, async session factory |
| `api/src/shared/storage.py` | **Create** | boto3 R2 client, `generate_presigned_put/get`, lifecycle config |
| `api/src/features/assets/router.py` | **Create** | `/projects`, `/projects/{id}/upload-ticket`, `/assets/{id}/finalize`, `DELETE /assets/{id}` |
| `api/src/features/assets/service.py` | **Create** | Business logic: ownership validation, presigned URL generation, soft-delete |
| `api/src/features/assets/models.py` | **Create** | Pydantic v2 schemas: `ProjectCreate`, `AssetResponse`, `UploadTicketResponse` |
| `api/src/shared/flows/base.py` | **Modify** | Add `asset_id: Optional[str]` to `ImageArtifact`, accept `image/webp`, ownership guard uses asset_id |
| `api/src/features/generation/modal_tasks.py` | **Modify** | ComfyUI save as WebP@90% (Pillow); install `LoadImageFromUrl` node |
| `api/src/shared/modal_config.py` | **Modify** | Inject `LoadImageFromUrl` node into ComfyUI image, add R2 env vars, `boto3` pip install |
| `api/app.py` | **Modify** | Include `assets_router`, register DB engine startup/shutdown |
| `view/src/features/assets/infrastructure/api.ts` | **Create** | `requestUploadTicket()`, `finalizeAsset()`, `deleteAsset()` API clients |
| `view/src/features/assets/application/use-upload.ts` | **Create** | Upload state machine hook: idle→compressing→requesting→uploading→done\|error |
| `view/src/features/assets/presentation/components/AssetsDrawer.tsx` | **Modify** | Replace `FileReader`+`dataUrl` with compression pipeline + R2 upload |
| `view/src/app/studio-state.ts` | **Modify** | Remove `dataUrl` from `Asset`, add `uploadStatus` + `r2Url` fields |
| `view/src/shared/infrastructure/api-client.ts` | **Modify** | Add `fetchWithSession()` helper reused by assets endpoints |

## Interfaces / Contracts

```python
# Pydantic v2 schemas
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)

class AssetResponse(BaseModel):
    id: str
    name: str
    content_type: str
    r2_key: str
    project_id: str
    created_at: datetime

class UploadTicketResponse(BaseModel):
    asset_id: str
    presigned_url: str          # PUT URL, expires 300s
    r2_key: str                 # object key to PUT

# ImageArtifact extension
class ImageArtifact(BaseModel):
    # ... existing fields +
    asset_id: Optional[str] = None   # NEW: resolved to presigned GET at dispatch time
```

```python
# R2 storage layer
class R2Storage:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket: str):
        self._client = boto3.client("s3", endpoint_url=endpoint_url, ...)
    def presigned_put(self, key: str, ttl: int = 300) -> str: ...
    def presigned_get(self, key: str, ttl: int = 300) -> str: ...
```

```typescript
// Frontend upload state machine
type UploadStatus = "idle" | "compressing" | "requesting_ticket"
                  | "uploading" | "done" | "error";

interface Asset {
  id: string; name: string; type: "image" | "file";
  r2Url: string;          // replaces dataUrl
  uploadStatus: UploadStatus;
  addedAt: string;
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (api) | ORM model `deleted_at` filter, `active_assets()` helper | pytest + in-memory SQLite |
| Unit (api) | `_validate_artifact_ownership` with `asset_id` | pytest, mock DB session |
| Unit (view) | `studioReducer` removes `dataUrl`, handles `uploadStatus` | vitest |
| Integration (api) | `POST /projects` → `POST /upload-ticket` → `PATCH /finalize` flow | pytest + httpx + in-memory SQLite |
| Integration (view) | Canvas compression → valid WebP ≤1024×1024 | vitest + jsdom |

## Migration / Rollout

No data migration required (users start with empty projects). Each chained PR is independently revertible per proposal. Frontend `dataUrl` is removed in slice 5 after R2 API is live.

## Open Questions

- [ ] Confirm R2 bucket CORS rules (allow PUT from frontend origin) — document in runbook
- [ ] Verify ComfyUI Pillow WebP support in Modal container image (python_version="3.10") — Pillow ≥9.1 required
