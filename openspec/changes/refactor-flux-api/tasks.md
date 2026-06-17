# Tasks: Refactor Flux 2 Generation API

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500–800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 |
| Delivery strategy | chained-pr |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No — user selected chained-pr with feature-branch-chain for PR 1.
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Models + Flux 2 workflows + tests | PR 1 | Models, JSON templates, manifests, and validation tests — no runtime wiring yet |
| 2 | Service + routing + config + cleanup | PR 2 | Service dispatch, router, app.py, modal_config, delete legacy dirs |

## Phase 1: Foundation — Models & Test Harness (TDD: RED→GREEN→REFACTOR)

- [x] 1.1 RED: Write failing test — `GenerateRequest` rejects legacy workflow values (`qwen_txt2img`, `realistic_persona`, etc.) and validates `use_turbo`, `image_base64`
- [x] 1.2 GREEN: Update `api/src/features/generation/models.py` — new `WorkflowName = Literal["flux2_txt2img", "flux2_editing", "identidad_gguf"]`, add `use_turbo: bool = True`, `image_base64: Optional[str]`, remove legacy fields (`checkpoint_url`, `lora_url`, `quality_mode`, etc.)
- [x] 1.3 REFACTOR: Consolidate model validators — remove `conflicting_aliases` logic for retired workflows, add `image_base64` + `use_turbo` cross-field validation

## Phase 2: Flux 2 Workflow Assets

- [x] 2.1 Create `api/src/workflows/flux2_txt2img/workflow.json` — copy from `~/Downloads/image_flux2_text_to_image.json`
- [x] 2.2 Create `api/src/workflows/flux2_txt2img/manifest.yaml` — map `prompt→"98:6".text`, `use_turbo→"98:104".value`, declare Flux 2 model defaults
- [x] 2.3 Create `api/src/workflows/flux2_editing/workflow.json` — copy from `~/Downloads/image_flux2_editing.json`, replace `LoadImage` node "46" with `LoadImageFromBase64`
- [x] 2.4 Create `api/src/workflows/flux2_editing/manifest.yaml` — map `prompt→"68:6".text`, `use_turbo→"68:94".value`, `image_base64→"46".image_url`

## Phase 3: Service & Routing (TDD: RED→GREEN→REFACTOR)

- [x] 3.1 RED: Write failing test — `enqueue_modal_work` routes `flux2_txt2img`/`flux2_editing`/`identidad_gguf` correctly via mocked WorkflowEngine
- [x] 3.2 GREEN: Update `api/src/features/generation/service.py` — remove Qwen/product/persona dispatch, add flux2 branches, inline `image_url→base64` for `flux2_editing`, prune `enqueue_modal_work` signature
- [x] 3.3 GREEN: Update `api/src/features/generation/router.py` — forward `use_turbo`, `image_base64` to `enqueue_modal_work`
- [x] 3.4 GREEN: Update `api/src/app.py` — remove `editing_router` and `controlnet_router` imports/registrations
- [x] 3.5 REFACTOR: Remove unused service helpers (`resolve_qwen_quality_defaults`, legacy workflow branches)

## Phase 4: Config & Cleanup

- [x] 4.1 RED: Write failing test — `modal_config` whitelist rejects legacy models (Qwen, SDXL checkpoints) and accepts Flux 2 models
- [x] 4.2 GREEN: Update `api/src/shared/modal_config.py` — prune whitelist to Flux 2 + identidad_gguf only
- [x] 4.3 Delete legacy workflow dirs: `qwen_txt2img/`, `realistic_persona/`, `product_premium/`, `txt2img/`, `controlnet/`, `img2img/`
- [x] 4.4 Delete legacy router dirs: `api/src/features/controlnet/`, `api/src/features/editing/`

## Phase 5: Integration Tests

- [x] 5.1 Integration test: `POST /generate` with `flux2_txt2img` returns 202 with `job_id`
- [x] 5.2 Integration test: `POST /generate` with `flux2_editing` + `image_base64` returns 202
- [x] 5.3 Integration test: Legacy workflows (`qwen_txt2img`, `txt2img`) return 422 with `unsupported_workflow`
