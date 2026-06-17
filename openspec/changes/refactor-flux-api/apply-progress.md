# Apply Progress: refactor-flux-api

## PR Slice

- Strategy: chained-pr
- Chain strategy: feature-branch-chain
- Tracker branch: `feature/refactor-flux-api`
- PR 1 branch: `feature/refactor-flux-api-pr1`
- PR 1 target: `feature/refactor-flux-api`
- PR 2 branch: `feature/refactor-flux-api-pr2`
- PR 2 target: `feature/refactor-flux-api-pr1`
- PR 1 boundary: Phases 1-2 — Pydantic request models, Flux 2 workflow assets, and asset validation tests.
- PR 2 boundary: Phases 3-5 — service/router/app runtime wiring, Modal whitelist cleanup, legacy workflow/router deletion, and integration tests.

## Completed Tasks

- [x] 1.1 RED: Write failing test — `GenerateRequest` rejects legacy workflow values and validates `use_turbo`, `image_base64`.
- [x] 1.2 GREEN: Update `api/src/features/generation/models.py` with Flux 2 workflow literals, `use_turbo`, `image_base64`, and retired legacy fields removed.
- [x] 1.3 REFACTOR: Consolidate workflow-scoped validators for image/turbo/identity fields.
- [x] 2.1 Create `api/src/workflows/flux2_txt2img/workflow.json` from the Flux 2 text-to-image export.
- [x] 2.2 Create `api/src/workflows/flux2_txt2img/manifest.yaml` with prompt/turbo mappings and Flux 2 defaults.
- [x] 2.3 Create `api/src/workflows/flux2_editing/workflow.json` from the Flux 2 editing export with node `46` replaced by `LoadImageFromBase64`.
- [x] 2.4 Create `api/src/workflows/flux2_editing/manifest.yaml` with prompt/turbo/image mappings and Flux 2 defaults.
- [x] 3.1 RED: Write failing service tests for Flux 2/identity routing and legacy workflow rejection.
- [x] 3.2 GREEN: Simplify `GenerationService.enqueue_modal_work` to Flux 2 + identidad_gguf only.
- [x] 3.3 GREEN: Update `/generate` router to forward `use_turbo` and `image_base64`.
- [x] 3.4 GREEN: Remove `editing_router` and `controlnet_router` registrations from `api/app.py`.
- [x] 3.5 REFACTOR: Remove Qwen/product/persona helpers and legacy dispatch paths.
- [x] 4.1 RED: Write whitelist tests proving legacy models are rejected and Flux 2/identity models remain accepted.
- [x] 4.2 GREEN: Prune `modal_config.py` whitelist and remove IPAdapter Plus install.
- [x] 4.3 Delete legacy workflow assets for Qwen, persona, product, txt2img, controlnet, and img2img.
- [x] 4.4 Delete legacy editing/controlnet router modules and tests.
- [x] 5.1 Integration test: `POST /generate` accepts `flux2_txt2img` with `202` and `job_id`.
- [x] 5.2 Integration test: `POST /generate` accepts `flux2_editing` with `image_base64`.
- [x] 5.3 Integration test: legacy workflows return `422` containing `unsupported_workflow`.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ New Flux 2/legacy rejection tests failed against old model (`18 failed, 30 passed`) | ✅ PR1 focused files passed | ✅ Multiple workflow values, retired fields, turbo true/false, image scope/required cases | ✅ Legacy model tests replaced with focused Flux 2 contract tests |
| 1.2 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ Tests referenced missing `use_turbo`, `image_base64`, and Flux 2 literals | ✅ PR1 focused files passed | ✅ Covered default txt2img, editing image, identity field scoping, and legacy values | ✅ Removed retired request fields and kept validator minimal |
| 1.3 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ Cross-field tests failed before validator update | ✅ PR1 focused files passed | ✅ Covered image_base64 required/forbidden, image_url scope, explicit identity turbo rejection | ✅ Consolidated validators into `validate_workflow_scoped_fields` |
| 2.1 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new workflow assets) | ✅ Missing `flux2_txt2img` workflow failed with `FileNotFoundError` | ✅ PR1 focused files passed | ✅ Engine test asserts graph resolves concrete prompt/turbo/default model fields | ✅ Wrapped API export under `prompt` for current WorkflowEngine contract |
| 2.2 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new manifest) | ✅ Missing manifest failed with `FileNotFoundError` | ✅ PR1 focused files passed | ✅ Manifest schema and engine resolution both verify mappings/defaults | ✅ Kept defaults locked and whitelist-validated |
| 2.3 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new workflow assets) | ✅ Missing `flux2_editing` workflow failed with `FileNotFoundError` | ✅ PR1 focused files passed | ✅ Test asserts node `46` is `LoadImageFromBase64` with `image_url` input | ✅ Replaced only the loader node and preserved the rest of the export |
| 2.4 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new manifest) | ✅ Missing manifest failed with `FileNotFoundError` | ✅ PR1 focused files passed | ✅ Engine test asserts prompt, turbo, image_base64, and model defaults resolve | ✅ Kept mappings aligned to design node IDs |
| 3.1 | `api/src/tests/test_generation_service.py` | Unit | ⚠️ Baseline had 30 expected pre-PR2 failures from legacy service/router drift after PR1 | ✅ Import/behavior failed before Flux 2 constants and routing existed | ✅ `34 passed` focused PR2 files | ✅ Covered txt2img, editing, identidad_gguf, and legacy rejection | ✅ Removed brittle legacy service tests and asserted behavior through resolved graphs |
| 3.2 | `api/src/tests/test_generation_service.py` | Unit | ⚠️ See 3.1 baseline | ✅ Service tests failed against Qwen/product/persona dispatch and old signature | ✅ Full suite `205 passed` | ✅ Standard Flux 2 spawn, heavy identity spawn, model cache validation | ✅ Pruned service to supported workflows and shared cache/model extraction |
| 3.3 | `api/src/tests/test_generation_router.py` | Integration | ⚠️ Router baseline failed on removed model fields (`request.format`) | ✅ Router tests failed until `use_turbo`/`image_base64` were forwarded | ✅ Full suite `205 passed` | ✅ Turbo false, editing base64, model_not_cached, model_not_allowed | ✅ Removed legacy router assertions |
| 3.4 | `api/src/tests/test_app.py` | Integration | ⚠️ App baseline imported legacy routers | ✅ App/router tests failed before router registrations were removed | ✅ Full suite `205 passed` | ✅ POST and WebSocket app-level smoke/behavior retained | ✅ App now mounts generation router only |
| 3.5 | `api/src/tests/test_generation_service.py` | Unit | ⚠️ Covered by 3.1 baseline | ✅ Legacy helper imports/expectations failed after tests were rewritten to Flux 2 contract | ✅ Full suite `205 passed` | ✅ Legacy workflow direct service calls reject before spawn | ✅ Deleted Qwen/product/persona helper code paths |
| 4.1 | `api/src/tests/test_modal_config.py` | Unit/config | ⚠️ Modal config baseline still expected legacy FaceID/IPAdapter assets | ✅ Whitelist tests failed while old Qwen/SDXL/IPAdapter entries remained | ✅ Full suite `205 passed` | ✅ Positive Flux 2/identity assertions plus negative legacy assertions | ✅ Kept Modal config assertions focused on supported assets |
| 4.2 | `api/src/tests/test_modal_config.py` | Unit/config | ⚠️ See 4.1 baseline | ✅ Config tests failed until whitelist and run commands were pruned | ✅ Full suite `205 passed` | ✅ Verifies Flux 2, identity GGUF, base64 node, and no IPAdapter Plus install | ✅ Removed obsolete whitelist categories from default JSON |
| 4.3 | `api/src/tests/test_workflow_templates.py` | Contract | ⚠️ Existing tests expected retired workflow assets | ✅ Contract tests failed until legacy workflow files were removed/expectations updated | ✅ Full suite `205 passed` | ✅ Verifies supported assets exist and retired workflow JSON/manifests do not | ✅ Replaced legacy template tests with supported workflow contract tests |
| 4.4 | `api/src/tests/test_generation_router.py` | Integration | ⚠️ Existing editing/controlnet router tests became obsolete | ✅ Deleted legacy router tests after router modules were removed | ✅ Full suite `205 passed` | ✅ App-level tests confirm generation router remains mounted | ✅ Removed legacy feature directories from tracked files |
| 5.1 | `api/src/tests/test_generation_router.py`, `api/src/tests/test_e2e_generation.py` | Integration | ✅ Covered by focused router/e2e baseline | ✅ Flux 2 txt2img endpoint test failed before router/service were wired | ✅ Full suite `205 passed` | ✅ Tests both router-local app and mounted app | ✅ Shared fixture whitelist/cache setup for Flux 2 |
| 5.2 | `api/src/tests/test_generation_router.py`, `api/src/tests/test_e2e_generation.py` | Integration | ✅ Covered by focused router/e2e baseline | ✅ Flux 2 editing endpoint test failed before base64 forwarding | ✅ Full suite `205 passed` | ✅ Asserts `image_base64` reaches `LoadImageFromBase64` graph | ✅ Kept editing coverage in generation endpoint only |
| 5.3 | `api/src/tests/test_generation_router.py`, `api/src/tests/test_e2e_generation.py` | Integration | ✅ Covered by focused router/e2e baseline | ✅ Legacy workflow tests failed until validation surfaced `unsupported_workflow` | ✅ Full suite `205 passed` | ✅ Parametrized `qwen_txt2img` and `txt2img` rejections | ✅ Added model pre-validator to preserve structured error code in 422 response |

## Test Summary

- Baseline before PR2 production edits: `python3 -m pytest src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_app.py src/tests/test_modal_config.py` → 70 passed, 30 failed. Failures were expected PR2 targets after PR1 removed model fields while service/router/config still referenced legacy behavior.
- RED: `python3 -m pytest src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_modal_config.py` → collection failed on missing `FLUX2_EDITING_WORKFLOW` / `FLUX2_TXT2IMG_WORKFLOW`, proving tests referenced not-yet-implemented service API.
- GREEN focused: `python3 -m pytest src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_modal_config.py` → 34 passed.
- PR1+PR2 relevant: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_flux2_workflow_assets.py src/tests/test_app.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_modal_config.py` → 85 passed.
- Final full suite: `python3 -m pytest` → 205 passed.
- Total tests written/updated in PR2: service, router, modal config, app, e2e, workflow engine/templates, modal task/cache/client cleanup tests.
- Layers used: Unit, integration, workflow contract.
- Approval/refactor tests: legacy contract tests rewritten to assert supported Flux 2 behavior and retired asset absence.

## Deviations

- `workflow.json` assets remain wrapped as `{ "prompt": ... }` because `WorkflowEngine` reads `template["prompt"]`.
- `unsupported_workflow` is returned inside FastAPI's 422 validation detail, matching Phase 5.3 task wording.
- Ignored `__pycache__` folders may remain locally, but tracked legacy router/workflow files are deleted and tests assert retired `workflow.json`/`manifest.yaml` files are gone.

## Remaining Tasks

- [x] All planned PR 1 and PR 2 apply tasks are complete.
