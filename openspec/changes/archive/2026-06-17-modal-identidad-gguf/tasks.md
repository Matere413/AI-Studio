# Tasks: Modal Identidad GGUF Workflow

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350–420 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-always |
| Chain strategy | pending |

```
Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium
```

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | All infra, workflow template, service routing, and tests | PR 1 | Single focused change; main branch; self-contained |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Add 3 `git clone` commands in `api/src/shared/modal_config.py` for `ComfyUI-GGUF`, PuLID Flux, `ComfyUI-Impact-Pack`
- [x] 1.2 Extend `default_whitelist` in `modal_config.py` with `gguf`, `pulid`, `face_detector`, `clip` categories and required filenames
- [x] 1.3 Add `gguf`/`pulid`/`face_detector` subdir resolution to `api/src/shared/workflows/cache.py`

## Phase 2: Core Implementation

- [x] 2.1 Create `api/src/workflows/identidad_gguf/workflow.json` — normalized template with `LoadImageFromBase64` replacing original `LoadImage`
- [x] 2.2 Create `api/src/workflows/identidad_gguf/manifest.yaml` — declare `prompt`→node4, `image_url`→node6, `width`/`height`→node5, `seed`→node11; defaults 1024×1024, seed=-1
- [x] 2.3 Add `"identidad_gguf"` to `WorkflowName` literal in `api/src/features/generation/models.py`
- [x] 2.4 Add `IDENTIDAD_GGUF_WORKFLOW` constant and `download_image_to_base64()` helper in `api/src/features/generation/service.py`
- [x] 2.5 Add `gguf`/`pulid`/`face_detector`/`clip` to `MODEL_TYPE_BY_SEMANTIC_NAME` mapping in `service.py`
- [x] 2.6 Route `identidad_gguf` to `run_generation_heavy` in `service.py` with base64-encoded image injection
- [x] 2.7 Pass `image_url` from `router.py` to `enqueue_modal_work` for identidad_gguf requests

## Phase 3: Testing / Verification

- [x] 3.1 Test: `validate_models` rejects non-whitelisted gguf/pulid models (spec: GGUF UNET not whitelisted → 400)
- [x] 3.2 Test: `enqueue_modal_work` resolves identidad_gguf and encodes image_url to base64 (spec: reference image injected)
- [x] 3.3 Test: Manifest loads without unknown node/field references (spec: workflow engine loads valid def)
- [x] 3.4 Test: POST /generate returns 202 for identidad_gguf with prompt+image_url (spec: request accepted)
- [x] 3.5 Test: POST /generate returns 400 when GGUF UNET not whitelisted (spec: model_not_allowed)

## Phase 4: Cleanup / Documentation

- [x] 4.1 Remove hardcoded local image path remnants from downloaded workflow if any remain
- [ ] 4.2 Verify cached models (`flux1-dev-q4_k_m.gguf`, `t5xxl_fp8_e4m3fn.safetensors`, `pulid_flux_v0.9.1.safetensors`, `face_yolov8m.onnx`) exist in Modal Volume
