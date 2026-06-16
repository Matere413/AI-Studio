# Tasks: Qwen Text-to-Image Pipeline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~410-475 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation + template) → PR 2 (Service + wiring + tests) |
| Delivery strategy | ask-always |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Template + manifest + dimension validator + unit tests | PR 1 | Base: `main`. ~200-250 lines. Verifiable standalone. |
| 2 | Request model + service logic + router wiring + integration tests | PR 2 | Base: `main`. Depends on PR 1 template. ~200-250 lines. |

## Phase 1: Foundation — Template + Dimension Validator

- [x] 1.1 Add `validate_dimensions()` helper to `api/src/shared/workflows/models.py` — multiple-of-64, range [256,2048], pixel budget ≤4,194,304
- [x] 1.2 Create `api/src/workflows/qwen_txt2img/workflow.json` — simplified Qwen graph wrapped in `"prompt"`, no custom switch nodes
- [x] 1.3 Create `api/src/workflows/qwen_txt2img/manifest.yaml` — declare all inputs with quality-mode defaults table
- [x] 1.4 Write unit tests for `validate_dimensions()` — valid/invalid widths, heights, pixel budgets

## Phase 2: Core — Request Model + Service Logic

- [x] 2.1 Extend `WorkflowName` Literal in `api/src/features/generation/models.py` with `"qwen_txt2img"`
- [x] 2.2 Add `width`, `height`, `quality_mode` fields + `@model_validator` to `GenerateRequest` — validates dimensions, constrains quality_mode to `fast|high`
- [x] 2.3 Implement quality mode defaults resolution in `service.py` — `fast`→4 steps/CFG 1.5/euler/sgm_uniform, `high`→50/7.0/euler_ancestral/normal
- [x] 2.4 Implement Lightning LoRA conditional node injection in `service.py` — when `quality_mode="fast"`, insert `LoraLoaderModelOnly` node and redirect KSampler model input

## Phase 3: Integration — Router Wiring

- [x] 3.1 Pass `width`, `height`, `quality_mode` from `router.py` to `service.enqueue_modal_work()`

## Phase 4: Testing

- [x] 4.1 Unit: quality mode defaults resolution — verify `fast`/`high` sampler params match design table
- [x] 4.2 Unit: Lightning LoRA injection — assert resolved graph contains LoRA node with redirected KSampler model input
- [x] 4.3 Unit: Qwen manifest reference validation — engine rejects missing node/field references
- [x] 4.4 Integration: full `POST /generate` with `workflow="qwen_txt2img"` → resolved graph (mock Modal spawn)
- [x] 4.5 Integration: missing Qwen model → `model_not_allowed` / `model_not_cached` errors

## Phase 5: Cleanup — Config

- [x] 5.1 Update `ALLOWED_MODELS_JSON` env var with Qwen FP8 UNET, CLIP, VAE, and Lightning LoRA filenames
