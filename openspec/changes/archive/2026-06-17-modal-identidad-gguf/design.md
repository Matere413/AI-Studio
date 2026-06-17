# Design: Modal Identity GGUF Workflow

## Technical Approach

Normalize the `identidad_gguf.json` workflow into the existing engine/manifest pattern. Install GGUF + PuLID + Impact Pack custom nodes via `modal.Image.run_commands`, extend the model whitelist with new categories (`gguf`, `pulid`, `face_detector`), replace the hardcoded `LoadImage` node with the existing `LoadImageFromBase64` custom node, and route the workflow through `run_generation_heavy` (L4 GPU, 900s timeout).

## Architecture Decisions

### Decision: Custom Node Installation Strategy

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Clone via `modal.Image.run_commands` | Immutable image, rebuild on change | **Chosen** |
| Install at runtime via ComfyUI Manager | Flexible, but violates V1 no-download boundary | Rejected |

**Rationale**: Follows existing pattern (IPAdapter_Plus cloned in `comfyui_run_commands`). Keeps the Modal image self-contained and deterministic.

### Decision: Reference Image Input Mechanism

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Replace template `LoadImage` with `LoadImageFromBase64` + download+encode in service | Reuses baked-in custom node; download happens pre-execution | **Chosen** |
| Download image to `/input/` directory and keep `LoadImage` | Requires write to Volume in Modal container, fragile | Rejected |

**Rationale**: The `LoadImageFromBase64` node is already baked. Downloading the HTTP URL → base64 encoding happens in the service layer BEFORE the graph is sent to Modal, keeping the Modal task side-effect-free.

### Decision: GPU and Routing

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `run_generation_heavy` (L4, 900s) | 24GB VRAM, same tier as Qwen | **Chosen** |
| `run_generation` (T4, 300s) | 16GB VRAM, insufficient for Flux GGUF + PuLID + FaceDetailer | Rejected |

**Rationale**: Flux UNET at Q4_K_M quantization (~6.8GB) + T5 CLIP (~9.6GB) + PuLID model (~1.5GB) pushes T4 beyond its VRAM budget. L4 with extended timeout is correct.

## Data Flow

```
POST /generate { workflow: "identidad_gguf", prompt, image_url }
  │
  ▼
router.py ──► GenerationService.enqueue_modal_work()
  │
  ├─ 1. Validate models: gguf, clip, pulid, face_detector in whitelist
  ├─ 2. Download image_url → base64 encode (httpx)
  ├─ 3. Resolve workflow via WorkflowEngine(manifest + template)
  │     └─ Injects: prompt→node4, image_url(data: URI)→node6, width/height→node5, seed→node11
  ├─ 4. Spawn run_generation_heavy.spawn(job_id, graph)
  │
  ▼
modal_tasks.run_generation_heavy ──► _execute_generation()
  │
  ├─ Boot ComfyUI with GGUF + PuLID + Impact Pack nodes available
  ├─ Queue prompt → poll progress via WebSocket
  └─ Return image_path → WS completion event → GET /images/{job_id}
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/modal_config.py` | Modify | Add 3 `git clone` commands for GGUF, PuLID, Impact Pack; extend `default_whitelist` JSON with `gguf`, `pulid`, `face_detector`, `clip` categories and required model filenames |
| `api/src/features/generation/models.py` | Modify | Add `"identidad_gguf"` to `WorkflowName` literal |
| `api/src/features/generation/service.py` | Modify | Add `IDENTIDAD_GGUF_WORKFLOW` constant; download + base64-encode `image_url` before injection; add `gguf`/`pulid`/`face_detector`/`clip` to `MODEL_TYPE_BY_SEMANTIC_NAME`; route `identidad_gguf` to `run_generation_heavy`; extend `validate_models` with new model types |
| `api/src/features/generation/router.py` | Modify | Pass `image_url` to `enqueue_modal_work` for identidad_gguf (already supported via existing param) |
| `api/src/workflows/identidad_gguf/workflow.json` | Create | Normalized template: replace node 6 `LoadImage` with `LoadImageFromBase64` (injectable), clean up hardcoded local path |
| `api/src/workflows/identidad_gguf/manifest.yaml` | Create | Declare inputs: `prompt`→node4, `image_url`→node6, `width`→node5, `height`→node5, `seed`→node11; defaults: 1024×1024, seed=-1 |
| `api/src/shared/workflows/cache.py` | Modify | Add `gguf`/`pulid`/`face_detector` subdir resolution to `resolve_cached_model` via existing `model_type` mapping |

## Interfaces / Contracts

**Whitelist extension** (new keys in `ALLOWED_MODELS_JSON`):

```json
{
  "gguf": ["flux1-dev-q4_k_m.gguf"],
  "pulid": ["pulid_flux_v0.9.1.safetensors"],
  "face_detector": ["face_yolov8m.onnx"],
  "clip": ["t5xxl_fp8_e4m3fn.safetensors"]
}
```

**`validate_models` new signature parameters**: `gguf: Optional[str]`, `pulid: Optional[str]`, `face_detector: Optional[str]`

**Manifest inputs contract**:
```yaml
inputs:
  prompt: { node_id: "4", field: "text" }
  image_url: { node_id: "6", field: "image_url" }
  width: { node_id: "5", field: "width" }
  height: { node_id: "5", field: "height" }
  seed: { node_id: "11", field: "seed" }
defaults:
  width: 1024
  height: 1024
  seed: -1
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `validate_models` rejects non-whitelisted gguf/pulid models | Parametrized pytest |
| Unit | `enqueue_modal_work` resolves identidad_gguf and encodes image_url to base64 | Mock httpx download |
| Contract | Manifest loads without unknown node/field references | `WorkflowEngine` init test |
| Contract | POST /generate returns 202 for identidad_gguf with prompt+image_url | FastAPI TestClient |
| Contract | POST /generate returns 400 when GGUF UNET not whitelisted | TestClient + monkeypatched whitelist |
| Integration | End-to-end: submit identidad_gguf → Modal returns image | Manual (requires Modal deployment) |

## Migration / Rollout

No migration required. New workflow is additive. Rollback: remove `identidad_gguf` routing, workflow files, whitelist entries, and 3 `git clone` lines from `modal_config.py`; redeploy previous Modal image.

## Open Questions

- [ ] What is the exact GitHub URL for PuLID Flux ComfyUI nodes? (`cubiq/PuLID_ComfyUI` appears to be the community standard — verify).
- [ ] `PulidFluxEvaClipLoader` and `PulidFluxInsightFaceLoader` auto-download model files on first run — does this violate V1 no-download boundary? Mitigation: first boot caches these in Volume; subsequent runs are cached.
- [ ] Should `face_yolov8m.onnx` be nested under `models/face_yolov8m/` (as the template uses) or flat under `models/face_detector/`?
