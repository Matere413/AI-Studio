# Apply Progress: refactor-flux-api

## PR Slice

- Strategy: chained-pr
- Chain strategy: feature-branch-chain
- Tracker branch: `feature/refactor-flux-api`
- PR 1 branch: `feature/refactor-flux-api-pr1`
- PR 1 target: `feature/refactor-flux-api`
- Boundary: Phases 1-2 only — Pydantic request models, strict-TDD model tests, Flux 2 workflow assets, and asset validation tests. Runtime service/router/config cleanup remains out of scope for PR 1.

## Completed Tasks

- [x] 1.1 RED: Write failing test — `GenerateRequest` rejects legacy workflow values and validates `use_turbo`, `image_base64`.
- [x] 1.2 GREEN: Update `api/src/features/generation/models.py` with Flux 2 workflow literals, `use_turbo`, `image_base64`, and retired legacy fields removed.
- [x] 1.3 REFACTOR: Consolidate workflow-scoped validators for image/turbo/identity fields.
- [x] 2.1 Create `api/src/workflows/flux2_txt2img/workflow.json` from the Flux 2 text-to-image export.
- [x] 2.2 Create `api/src/workflows/flux2_txt2img/manifest.yaml` with prompt/turbo mappings and Flux 2 defaults.
- [x] 2.3 Create `api/src/workflows/flux2_editing/workflow.json` from the Flux 2 editing export with node `46` replaced by `LoadImageFromBase64`.
- [x] 2.4 Create `api/src/workflows/flux2_editing/manifest.yaml` with prompt/turbo/image mappings and Flux 2 defaults.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ New Flux 2/legacy rejection tests failed against old model (`18 failed, 30 passed`) | ✅ `48 passed` for PR1 files | ✅ Multiple workflow values, retired fields, turbo true/false, image scope/required cases | ✅ Legacy model tests replaced with focused Flux 2 contract tests |
| 1.2 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ Tests referenced missing `use_turbo`, `image_base64`, and Flux 2 literals | ✅ `48 passed` for PR1 files | ✅ Covered default txt2img, editing image, identity field scoping, and legacy values | ✅ Removed retired request fields and kept validator minimal |
| 1.3 | `api/src/tests/test_generation_models.py` | Unit | ✅ 51/51 baseline model tests passed | ✅ Cross-field tests failed before validator update | ✅ `48 passed` for PR1 files | ✅ Covered image_base64 required/forbidden, image_url scope, explicit identity turbo rejection | ✅ Consolidated validators into `validate_workflow_scoped_fields` |
| 2.1 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new workflow assets) | ✅ Missing `flux2_txt2img` workflow failed with `FileNotFoundError` | ✅ `48 passed` for PR1 files | ✅ Engine test asserts graph resolves concrete prompt/turbo/default model fields | ✅ Wrapped API export under `prompt` for current WorkflowEngine contract |
| 2.2 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new manifest) | ✅ Missing manifest failed with `FileNotFoundError` | ✅ `48 passed` for PR1 files | ✅ Manifest schema and engine resolution both verify mappings/defaults | ✅ Kept defaults locked and whitelist-validated |
| 2.3 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new workflow assets) | ✅ Missing `flux2_editing` workflow failed with `FileNotFoundError` | ✅ `48 passed` for PR1 files | ✅ Test asserts node `46` is `LoadImageFromBase64` with `image_url` input | ✅ Replaced only the loader node and preserved the rest of the export |
| 2.4 | `api/src/tests/test_flux2_workflow_assets.py` | Unit/contract | N/A (new manifest) | ✅ Missing manifest failed with `FileNotFoundError` | ✅ `48 passed` for PR1 files | ✅ Engine test asserts prompt, turbo, image_base64, and model defaults resolve | ✅ Kept mappings aligned to design node IDs |

## Test Summary

- Baseline before production model edits: `python3 -m pytest src/tests/test_generation_models.py` → 51 passed.
- RED: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_flux2_workflow_assets.py` → 18 failed, 30 passed.
- GREEN/REFACTOR: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_flux2_workflow_assets.py` → 48 passed.
- Full suite check: `python3 -m pytest` → 260 passed, 42 failed. Failures are expected outside PR 1 boundary because service/router/config still reference legacy fields and workflows scheduled for Phases 3-4; several unrelated existing identity/cache/modal tests also fail.

## Deviations

- `workflow.json` assets are wrapped as `{ "prompt": ... }` instead of storing the raw downloaded node map because the existing `WorkflowEngine` contract reads templates from `template["prompt"]`.

## Remaining Tasks

- [ ] Phase 3: Service & routing changes.
- [ ] Phase 4: Modal config and legacy cleanup.
- [ ] Phase 5: Integration tests.
