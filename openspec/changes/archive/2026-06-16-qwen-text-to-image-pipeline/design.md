# Design: Qwen Text-to-Image Pipeline

## Technical Approach

Add `qwen_txt2img` as a new workflow template following the existing `workflow.json` + `manifest.yaml` pattern. The source Qwen JSON (flat structure with custom switch/primitive nodes) is simplified into a clean standard ComfyUI graph wrapped in `"prompt"`. Quality-mode branching (fast Lightning vs high quality) is resolved by the service layer before graph execution — two separate resolved graphs are produced based on `quality_mode`, not by runtime switch nodes. Dimension validation (multiple of 64, range, pixel budget) happens at the Pydantic schema level in `GenerateRequest`.

## Architecture Decisions

| Decision | Option | Tradeoff | Choice |
|----------|--------|----------|--------|
| Quality mode resolution | Two workflows vs one workflow + service branching | Two workflows = more files; one = more complex manifest | **One workflow + service branching** — `quality_mode` is a request param; service selects defaults and manifest mappings |
| Custom switch nodes | Keep ComfySwitchNode vs strip to standard nodes | Keep = exact source fidelity; strip = no custom node deps | **Strip to standard nodes** — avoids installing custom nodes in ComfyUI image |
| Template format | Flat JSON + engine change vs `"prompt"`-wrapped | Engine change = broader impact; wrap = follows existing pattern | **Wrap in `"prompt"`** — existing `_load_graph_from_dict` expects this key |
| Dimension validation | Pydantic validator vs engine-level check | Pydantic = early rejection; engine = late failure | **Pydantic `@model_validator`** — fail fast with HTTP 422 |
| Lightning LoRA injection | Separate template vs conditional node insertion | Separate = duplication; conditional = service logic | **Conditional node insertion** — service adds LoRA node to graph when `quality_mode="fast"` |

## Data Flow

```
Client POST /generate
    │
    ▼
GenerateRequest (Pydantic validation: dimensions, quality_mode)
    │
    ▼
GenerationService.enqueue_modal_work()
    ├── validate_models() — whitelist check (Qwen UNET, CLIP, VAE, Lightning LoRA)
    ├── resolve_cached_model() — Volume presence check
    ├── WorkflowEngine.execute(params) — apply manifest mappings
    │     └── quality_mode="fast" → inject LoRA node, set 4 steps/CFG 1.5
    │     └── quality_mode="high" → no LoRA, set 50 steps/CFG 7.0
    │
    ▼
run_generation.spawn(job_id, resolved_graph) — Modal GPU
    │
    ▼
ComfyUI execution → SaveImage → image_volume.commit
    │
    ▼
Webhook / WebSocket → client
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/workflows/qwen_txt2img/workflow.json` | Create | Simplified Qwen graph (no switch/primitive nodes), wrapped in `"prompt"` |
| `api/src/workflows/qwen_txt2img/manifest.yaml` | Create | Declares `prompt`, `negative_prompt`, `width`, `height`, `quality_mode`, `steps`, `cfg`, `sampler_name`, `sampler_scheduler` inputs with defaults |
| `api/src/features/generation/models.py` | Modify | Add `"qwen_txt2img"` to `WorkflowName` Literal; add `width`, `height`, `quality_mode` fields with Pydantic validators |
| `api/src/features/generation/service.py` | Modify | Extend `enqueue_modal_work()` to handle `width`, `height`, `quality_mode` params; inject Lightning LoRA node conditionally |
| `api/src/features/generation/router.py` | Modify | Pass `width`, `height`, `quality_mode` to `enqueue_modal_work()` |
| `api/src/shared/workflows/models.py` | Modify | Add `DimensionValidator` mixin or helper for multiple-of-64 + range validation |
| `api/src/shared/workflows/cache.py` | No change | Whitelist entries added via `ALLOWED_MODELS_JSON` env var, no code change |

## Interfaces / Contracts

### GenerateRequest additions (models.py)

```python
WorkflowName = Literal["txt2img", "img2img", "controlnet", "product_premium", "realistic_persona", "qwen_txt2img"]

# New fields on GenerateRequest:
width: Optional[int] = Field(None, ge=256, le=2048)
height: Optional[int] = Field(None, ge=256, le=2048)
quality_mode: Literal["fast", "high"] = Field("high")
```

### Dimension validator (shared helper)

```python
def validate_dimensions(width: int, height: int) -> None:
    """Raise ValueError if dimensions are invalid for ComfyUI."""
    MAX_PIXELS = 4_194_304  # ~2048x2048
    if width % 64 != 0 or height % 64 != 0:
        raise ValueError("invalid_dimensions: width and height must be multiples of 64")
    if width * height > MAX_PIXELS:
        raise ValueError("invalid_dimensions: total pixels exceed 4,194,304")
```

### Qwen manifest defaults (manifest.yaml)

```yaml
defaults:
  width: 1024
  height: 1024
  quality_mode: "high"
  steps: 50
  cfg: 7.0
  sampler_name: "euler_ancestral"
  sampler_scheduler: "normal"
```

### Quality mode resolution table

| quality_mode | steps | cfg | sampler_name | scheduler | Lightning LoRA |
|---|---|---|---|---|---|
| `"high"` (default) | 50 | 7.0 | `euler_ancestral` | `normal` | disabled |
| `"fast"` | 4 | 1.5 | `euler` | `sgm_uniform` | enabled |

### Lightning LoRA node injection

When `quality_mode="fast"`, the service inserts a `LoraLoaderModelOnly` node into the resolved graph before the KSampler, pointing to the Lightning LoRA file. The KSampler's `model` input is redirected from the UNET output to the LoRA output.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Dimension validation (multiples of 64, range, pixel budget) | Pydantic validator unit tests with valid/invalid inputs |
| Unit | Quality mode defaults resolution | Verify `fast` → 4 steps/CFG 1.5, `high` → 50 steps/CFG 7.0 |
| Unit | Lightning LoRA node injection | Assert graph contains LoRA node and KSampler model input is redirected |
| Unit | Manifest load validation | Verify Qwen manifest references valid node IDs in template |
| Integration | Full `qwen_txt2img` request → resolved graph | End-to-end from POST /generate to graph resolution (mock Modal spawn) |
| Integration | Model whitelist + cache validation | Test missing Qwen model → `model_not_allowed` / `model_not_cached` |

## Migration / Rollout

No migration required. The change is additive — new workflow name, new files, new request fields. Existing workflows are unaffected. Rollout requires:
1. Qwen model files pre-cached in Modal Volume
2. `ALLOWED_MODELS_JSON` updated with Qwen model filenames
3. Deploy new API code

## Open Questions

- [ ] Confirm exact Lightning LoRA filename matches what will be cached in the Modal Volume
- [ ] Verify T4 GPU has sufficient VRAM for Qwen FP8 UNET at 1024×1024 (may need A10G upgrade for high-quality mode)
- [ ] Decide whether `shift=3.1` (ModelSamplingAuraFlow) should be a manifest default or hardcoded in the template
