# Apply Progress: refactor-flux-api

## PR Slice

- Strategy: chained-pr
- Chain strategy: feature-branch-chain
- Tracker branch: `feature/refactor-flux-api`
- PR 1 branch: `feature/refactor-flux-api-pr1`
- PR 1 target: `feature/refactor-flux-api`
- PR 2 branch: `feature/refactor-flux-api-pr2`
- PR 2 target: `feature/refactor-flux-api-pr1`
- PR 3 branch: `feature/refactor-flux-api-pr3`
- PR 3 target: `feature/refactor-flux-api-pr2`
- PR 1 boundary: Phases 1-2 — Pydantic request models, Flux 2 workflow assets, and asset validation tests.
- PR 2 boundary: Phases 3-5 — service/router/app runtime wiring, Modal whitelist cleanup, legacy workflow/router deletion, and integration tests.
- PR 3 boundary: Phase 6 — Frontend alignment: types, store, client, hook, and PromptPanel refactored for Flux 2 workflows.
- PR 4 branch: `feature/refactor-flux-api-pr4`
- PR 4 target: `feature/refactor-flux-api-pr3`
- PR 4 boundary: Phase 7 — Frontend polish: viewport-constrained layout and layout stability when switching workflows.

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
- [x] All planned PR 3 (Phase 6) apply tasks are complete.
- [x] All planned PR 4 (Phase 7) apply tasks are complete.

## Phase 6 TDD Cycle Evidence (PR 3 — Frontend Alignment)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 6.1 | `view/src/features/generation/stores/generationStore.test.ts` | Unit | ✅ 143 baseline tests passed | ✅ New legacy-rejection and Flux 2 acceptance tests failed against old store constants | ✅ All store tests pass | ✅ Covered: `flux2_txt2img`, `flux2_editing`, `identidad_gguf` acceptance; legacy `txt2img`/`img2img`/`controlnet`/`product_premium`/`realistic_persona`/`qwen_txt2img` rejection; turbo default toggling; editing image requirement | ✅ Removed `PERSONA_FIELDS`, `PERSONA_STRING_FIELDS`, `removePersonaFields`, `removeEmptyPersonaStrings`, product/persona normalization |
| 6.2 | `view/src/features/generation/api/types.ts` | Types | N/A (type-only change) | ✅ Store tests failed against old types with legacy `WorkflowName`, `ProductFormat`, `PersonaOutputType` values | ✅ TypeScript compilation clean, all tests pass | ✅ Covered: new `WorkflowName` literals, `use_turbo`/`image_base64` fields in `GenerationParameters` | ✅ Removed `ProductFormat`, `PersonaOutputType`, and all legacy fields from `GenerationParameters` |
| 6.3 | `view/src/features/generation/stores/generationStore.test.ts` | Unit | ✅ 41 store tests passing | ✅ Flux 2 normalization, turbo defaults, editing image validation all failed before store refactor | ✅ All 41 store tests pass | ✅ Covered: `flux2_txt2img` defaults turbo, editing strips identity fields, identity strips turbo fields | ✅ Cleaned `normalizeParameters` to workflow-scoped logic |
| 6.4 | `view/src/features/generation/stores/generationStore.ts` | Store | ✅ 41 tests passed | ✅ See 6.3 | ✅ All 41 tests pass | ✅ See 6.3 | ✅ Replaced legacy constants with Flux 2+identity `VALID_WORKFLOWS`; `clearReferenceFace` now also clears `image_base64` |
| 6.5 | `view/src/features/generation/api/client.test.ts` | Unit | ✅ 10 baseline client tests passed | ✅ Legacy workflow payload tests failed after type changes (old `GenerationParameters` with `txt2img`/`controlnet` rejected) | ✅ All 10 rewritten client tests pass | ✅ Covered: `flux2_txt2img` turbo default, `flux2_editing` with `image_base64`, `identidad_gguf` with `image_url`/dimensions/seed, no turbo for identity, no `image_base64` for txt2img | ✅ Removed `PERSONA_STRING_FIELDS` and legacy field-by-field payload construction |
| 6.6 | `view/src/features/generation/api/client.ts` | API | ✅ 10 tests pass | ✅ See 6.5 | ✅ All 10 tests pass | ✅ See 6.5 | ✅ Replaced legacy payload with workflow-scoped field mapping |
| 6.7 | `view/src/features/generation/hooks/useGenerationFlow.test.tsx` | Integration | ✅ 11 baseline hook tests passed | ✅ Legacy persona/txt2img flow tests failed after types changed | ✅ All 11 rewritten hook tests pass | ✅ Covered: `flux2_txt2img` payload, `flux2_editing` with `image_base64`, identity with `image_url`, no reference for txt2img, error/cancel/reset flows | ✅ Replaced `realistic_persona`/`identidad_gguf` conditional with `identidad_gguf`/`flux2_editing` |
| 6.8 | `view/src/features/generation/hooks/useGenerationFlow.ts` | Hook | ✅ 11 tests pass | ✅ See 6.7 | ✅ All 11 tests pass | ✅ See 6.7 | ✅ Simplified `generate` callback to map `referenceFaceUrl` → `image_base64` for editing, `image_url` for identity |
| 6.9 | `view/src/features/generation/components/PromptPanel.test.tsx` | Integration | ✅ 27 PromptPanel tests passing after initial rewrite | ✅ Legacy workflow UI tests removed; new Flux 2 turbo/editing tests failed referencing new UI | ✅ All 27 PromptPanel tests pass | ✅ Covered: Flux 2 chip rendering, no legacy chips, turbo toggle on/off, editing image upload/validation/removal, identity reference, disabled states, submit payloads | ✅ Removed all legacy controls (persona, product, qwen, checkpoint/lora); extracted image upload handler for shared use by editing and identity |
| 6.10 | `view/src/features/generation/components/PromptPanel.tsx` | UI | ✅ 27 tests pass | ✅ See 6.9 | ✅ All 27 tests pass | ✅ See 6.9 | ✅ Replaced 7-workflow chip list with 3 Flux 2+identity chips; added turbo toggle section; conditionally renders reference image upload for editing+identity; removed all legacy-specific constants |
| 6.11 | All view test files | Full suite | ✅ 143 baseline tests passed (pre-PR3) | ✅ See individual tasks | ✅ 151 tests pass (all 14 test files) | ✅ Coverage includes: store (41), PromptPanel (27), useGenerationFlow (11), client (10), IdentitySettingsPanel (6), lib/api (7), plus canvas/terminal/history/etc. | ✅ Removed `src/lib/api.ts` legacy fields; updated all test fixtures from `txt2img`/`img2img`/`controlnet` to `flux2_txt2img`/`flux2_editing`/`identidad_gguf`; `IdentitySettingsPanel` activated for `flux2_editing` workflow |

## Phase 6 Test Summary

- Baseline before PR3: 143 passing tests across 14 test files.
- After PR3 types/store/client/hook/UI changes: 151 passing tests across 14 test files (8 new tests added: legacy rejection, turbo toggle, editing image, Flux 2 payload tests).
- TypeScript compilation: clean (0 errors).
- Layers used: Unit, integration, UI component.
- No approval tests needed for new code (all greenfield).

## Phase 6 Deviations

- `PromptPanel.tsx` turbo toggle uses a styled `<button>` instead of a native toggle input for design consistency with the existing chip design system.
- `IdentitySettingsPanel.tsx` was extended to activate for both `identidad_gguf` and `flux2_editing` workflows, reusing the existing reference image upload.
- `src/lib/api.ts` had legacy field references (`format`, `checkpoint_url`, `lora_url`) that were removed alongside the feature-scoped `client.ts` changes — this was not a separate task but a cascade fix required for TypeScript compilation.

## Phase 7 TDD Cycle Evidence (PR 4 — Frontend Polish: Layout Stability)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 7.1 | `GenerationStudio.test.tsx` | Integration | ✅ 7 baseline tests passed | ✅ New test failed — `data-viewport-constrained="true"` attribute missing on `.studio` | ✅ All 8 GenerationStudio tests pass after adding attribute | ✅ Added sidebar scroll assertion as second test case | ✅ No refactoring needed |
| 7.2 | `GenerationStudio.module.css` + `GenerationStudio.tsx` | CSS/UI | ✅ See 7.1 | ✅ See 7.1 | ✅ CSS `min-height: 100vh` → `height: 100vh` + `overflow: hidden`; mobile sidebar `auto` → `minmax(0, 40vh)` | N/A (CSS change) | ✅ Clean |
| 7.3 | `PromptPanel.test.tsx` | Integration | ✅ 27 baseline tests passed | ✅ 4 new tests failed — `getByTestId("turbo-section")` and `getByTestId("reference-section")` not found; 2 existing tests failed (expected elements to be absent but now hidden-in-DOM) | ✅ All 33 PromptPanel tests pass after component and test updates | ✅ Added: workflow switching toggles `data-hidden`, both sections visible for `flux2_editing`, turbo hidden for `identidad_gguf`, reference hidden for `flux2_txt2img` | ✅ Updated existing tests from `not.toBeInTheDocument()` to `toHaveAttribute("data-hidden", "true")` |
| 7.4 | `PromptPanel.tsx` + `PromptPanel.module.css` | UI | ✅ See 7.3 | ✅ See 7.3 | ✅ Conditional rendering (`{isFlux2Workflow && ...}`) → always-render with `sectionHidden` class + `data-hidden`/`aria-hidden`/`inert` attributes | ✅ Added `.sectionHidden` and `.toggleRow` CSS classes |
| 7.5 | `IdentitySettingsPanel.test.tsx` | Integration | ✅ 6 baseline tests passed | ✅ 2 new tests passed immediately (panel already renders persistently with `data-disabled`) | ✅ All 8 IdentitySettingsPanel tests pass | ✅ Verified `data-disabled` attribute on inactive workflow state | ✅ No changes needed — panel was already stable |
| 7.6 | No code changes needed — `IdentitySettingsPanel` already has stable layout | N/A | N/A | N/A | N/A | N/A | N/A |
| 7.7 | All view test files | Full suite | ✅ 151 baseline tests passed | ✅ See individual tasks | ✅ 161 tests pass (all 14 test files) | ✅ 10 new layout stability tests across GenerationStudio, PromptPanel, IdentitySettingsPanel | ✅ TypeScript compilation clean; no refactoring needed |

## Phase 7 Test Summary

- Baseline before PR4: 151 passing tests across 14 test files.
- After PR4 layout stability changes: 161 passing tests across 14 test files (10 new tests added).
- TypeScript compilation: clean (0 errors).
- Layers used: Integration, UI component.
- No approval tests needed (all greenfield modifications).

## Phase 7 Deviations

- None — implementation matches user's requirement: panels no longer jump/resize when switching workflows, viewport is constrained to `100vh`, and all content visible without page-level scrolling.
