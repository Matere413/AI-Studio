# Design: Persona Identity Preservation

## Technical Approach

Upgrade `realistic_persona` from prompt-only SDXL generation to optional IP-Adapter FaceID Plus V2 identity conditioning. The change spans four layers:

1. **ComfyUI graph** — add IP-Adapter nodes to the workflow; conditional activation via `faceid_strength` param (0 = disabled, ~0.75 = active).
2. **API layer** — accept `image_url` (base64 data URI) in `GenerateRequest`; forward to workflow params.
3. **Frontend** — file input converts to base64 data URI, stored in Zustand `referenceFaceUrl`, sent in generation payload.
4. **Modal infra** — whitelist + pre-cache RealVisXL_V4.0, FaceID adapter, CLIP Vision; install `ComfyUI_IPAdapter_plus` node.

Prompt-only generation remains the default when no `image_url` is provided — zero behavioral change for existing users.

## Architecture Decisions

### Decision: Single workflow with conditional IP-Adapter activation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single workflow.json, strength=0 to disable | Simpler engine usage; one template to maintain | **Chosen** |
| Two separate workflow files (prompt-only + faceid) | Clean separation but doubles manifest/graph maintenance | Rejected |
| Dynamic graph mutation in service | Breaks WorkflowEngine pattern; harder to test | Rejected |

**Rationale**: The WorkflowEngine expects a static template + manifest. Setting `faceid_strength` to 0 effectively disables the IP-Adapter nodes while keeping the graph valid. This avoids duplicating the entire workflow or mutating the engine contract.

### Decision: Base64 data URI for `image_url` (V1)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Base64 data URI in JSON payload | Simple, no infra changes; larger payload (~30% overhead) | **Chosen** |
| Upload to S3/R2, pass URL | Cleaner contract; requires storage infra not yet available | Rejected (V2) |
| Upload to Modal Volume via dedicated endpoint | Direct server-side access; adds API surface | Rejected (V2) |

**Rationale**: The project convention says "no base64 over primary API channels," but S3/R2 is not yet deployed. For V1, base64 data URI is the simplest path. The payload increase is acceptable for a single reference face image (<10MB → ~13MB base64). A custom `LoadImageFromUrl` node on the Modal side decodes the data URI and writes a temp file for ComfyUI.

### Decision: RealVisXL_V4.0 replaces juggernautXL_ragnarok

| Option | Tradeoff | Decision |
|--------|----------|----------|
| RealVisXL_V4.0 | Better photorealism; FaceID compatibility | **Chosen** |
| Keep juggernautXL_ragnarok | No checkpoint change; may have lower FaceID quality | Rejected |

**Rationale**: RealVisXL_V4.0 is the exploration-recommended checkpoint for SDXL identity preservation. The manifest default and whitelist both update.

### Decision: IP-Adapter-only on T4 (no InstantID)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| IP-Adapter FaceID Plus V2 only | ~11.3 GB VRAM; fits T4 comfortably | **Chosen** |
| InstantID + IP-Adapter stacked | Higher fidelity; ~15.9 GB, OOM risk on T4 | Rejected |

**Rationale**: InstantID pushes T4 to its limit. V1 stays IP-Adapter-only. Higher fidelity can be added later with A100 routing.

## Data Flow

```
Frontend                          API                              Modal / ComfyUI
─────────                         ───                              ─────────────────

User uploads image
  │
  ▼
Convert to base64 data URI
  │
  ▼
Store in Zustand
  │  referenceFaceUrl
  ▼
Submit POST /generate ──────► GenerateRequest validates ──► enqueue_modal_work
  │  { image_url: "data:..." }    image_url field              builds params
  │                                                             │
  │                                                             ▼
  │                                                    WorkflowEngine.resolve
  │                                                    (injects image_url +
  │                                                     faceid_strength=0.75)
  │                                                             │
  │                                                             ▼
  │                                                    run_generation spawns
  │                                                    ComfyUI with resolved graph
  │                                                             │
  │                                                             ▼
  │                                                    LoadImageFromBase64 node
  │                                                    decodes data URI → tensor
  │                                                             │
  │                                                             ▼
  │                                                    IP-Adapter FaceID applies
  │                                                    conditioning → KSampler
  │                                                             │
  ◄─────────────────────────────────────────────────────────────┘
  WebSocket events               WS poll events
  (booting → generating → done)
```

**Prompt-only fallback** (no `image_url`): same flow, but `faceid_strength=0` and `image_url=""`. IP-Adapter nodes execute with zero influence — output matches prompt-only generation.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/workflows/realistic_persona/workflow.json` | Modify | Add IP-Adapter FaceID nodes: LoadImageFromBase64, IPAdapterModelLoader, CLIPVisionLoader, IPAdapterFaceIDPlusV2. Wire model output into KSampler. |
| `api/src/workflows/realistic_persona/manifest.yaml` | Modify | Change `default_checkpoint` to `RealVisXL_V4.0.safetensors`. Add `image_url` and `faceid_strength` inputs. Update prompt template if needed. Remove `v1_excluded_nodes` IPAdapter entry. |
| `api/src/features/generation/models.py` | Modify | Add `image_url: Optional[str]` field to `GenerateRequest`. Add persona-scoped validation for `image_url` format (accepts http/https URLs or `data:` URIs). |
| `api/src/features/generation/service.py` | Modify | Pass `image_url` to params in `enqueue_modal_work`. Set `faceid_strength=0.75` when image present, `0` when absent. |
| `api/src/features/generation/router.py` | Modify | Forward `request.image_url` to `enqueue_modal_work`. |
| `api/src/shared/modal_config.py` | Modify | Add `RealVisXL_V4.0.safetensors` and FaceID adapter filenames to whitelist. Add `ComfyUI_IPAdapter_plus` git clone to `run_commands`. |
| `view/src/features/generation/api/types.ts` | Modify | Add `image_url?: string` to `GenerationParameters`. |
| `view/src/features/generation/api/client.ts` | Modify | Include `image_url` in submit payload when present. |
| `view/src/features/generation/stores/generationStore.ts` | Modify | Add `referenceFaceUrl: string \| null` to store state. Add `setReferenceFaceUrl` and `clearReferenceFace` actions. Include `image_url` in normalized persona params. |
| `view/src/features/generation/components/PromptPanel.tsx` | Modify | Add optional file upload control when `realistic_persona` active. Convert file to base64 data URI, call `setReferenceFaceUrl`. Show remove button. |
| `view/src/features/generation/hooks/useGenerationFlow.ts` | Modify | Read `referenceFaceUrl` from store, include in generation params as `image_url`. |

## Interfaces / Contracts

### New manifest inputs (`manifest.yaml`)

```yaml
inputs:
  image_url:
    node_id: "10"          # LoadImageFromBase64 node
    field: "image_url"
  faceid_strength:
    node_id: "12"          # IPAdapterFaceIDPlusV2 node
    field: "strength"
```

### New defaults

```yaml
defaults:
  # ... existing defaults ...
  faceid_strength: 0       # 0 = disabled (prompt-only fallback)
```

### GenerateRequest extension (`models.py`)

```python
image_url: Optional[str] = Field(
    None,
    description="Optional reference face image URL or base64 data URI for identity preservation."
)
```

### Zustand store extension (`generationStore.ts`)

```typescript
interface GenerationStore {
  // ... existing fields ...
  referenceFaceUrl: string | null;
  setReferenceFaceUrl(url: string | null): void;
  clearReferenceFace(): void;
}
```

### GenerationParameters extension (`types.ts`)

```typescript
export interface GenerationParameters {
  // ... existing fields ...
  image_url?: string;
}
```

### ComfyUI graph additions (`workflow.json`)

New nodes appended to existing graph:

```json
"10": {
  "inputs": { "image_url": "" },
  "class_type": "LoadImageFromBase64",
  "_meta": { "title": "Load Reference Face" }
},
"11": {
  "inputs": { "ipadapter_file": "ip-adapter-faceid-plusv2_sdxl.bin" },
  "class_type": "IPAdapterModelLoader",
  "_meta": { "title": "Load IP-Adapter Model" }
},
"12": {
  "inputs": {
    "image": ["10", 0],
    "ipadapter": ["11", 0],
    "clip_vision": ["13", 0],
    "model": ["4", 0],
    "strength": 0
  },
  "class_type": "IPAdapterFaceIDPlusV2",
  "_meta": { "title": "Apply FaceID" }
},
"13": {
  "inputs": { "clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" },
  "class_type": "CLIPVisionLoader",
  "_meta": { "title": "Load CLIP Vision" }
}
```

KSampler model input updated from `["4", 0]` to `["12", 0]` (IP-Adapter output). When `strength=0`, the model passes through unchanged.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `GenerateRequest` validates `image_url` format (URL, data URI, invalid) | Pytest parametrize on `models.py` |
| Unit | Manifest defaults include `faceid_strength: 0` | Pytest on manifest YAML load |
| Unit | `normalizeParameters` includes `image_url` for persona workflow | Jest on `generationStore.ts` |
| Unit | `setReferenceFaceUrl` / `clearReferenceFace` store actions | Jest on store |
| Unit | WorkflowEngine injects `image_url` and `faceid_strength` into resolved graph | Pytest on `engine.py` |
| Integration | `enqueue_modal_work` passes correct params with/without `image_url` | Pytest on `service.py` with mock engine |
| Integration | POST /generate accepts `image_url` and forwards to service | FastAPI TestClient |
| E2E | Full flow: upload image → generate → verify FaceID conditioning applied | Manual test on Modal (V1 no automated E2E) |

## Migration / Rollout

**No data migration required.** The change is additive:

1. **Whitelist update**: Add new model filenames — existing workflows unaffected.
2. **Manifest default change**: `juggernautXL_ragnarok` → `RealVisXL_V4.0` — only affects `realistic_persona` workflow.
3. **Frontend**: Upload control is optional — existing persona generation works unchanged.

**Rollback**: Revert manifest default to `juggernautXL_ragnarok`, remove `image_url`/`faceid_strength` inputs, hide upload UI, remove whitelist entries after active jobs drain.

## Open Questions

- [ ] Exact node `class_type` names for `ComfyUI_IPAdapter_plus` FaceID Plus V2 nodes — verify against installed node version on Modal.
- [ ] FaceID strength default value — 0.75 is a starting point; may need tuning based on visual results.
- [ ] Whether `LoadImageFromBase64` should be a custom node or if `ComfyUI_IPAdapter_plus` already provides one.
