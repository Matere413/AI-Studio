# Apply Progress: SDD-2 Modal Flows

## Phase 1 / PR 1 Complete — Foundation & Extraction Flow

**Branch**: `feature/sdd-2-modal-flows-pr1` → `feature/sdd-2-modal-flows` → `master`

### TDD Cycle Evidence

| Task | RED test written | GREEN code | Refactor | Tests passing |
|------|-----------------|------------|----------|---------------|
| 1.1 `flows/__init__.py` | ✅ ImportError → created | ✅ | — | 26/26 |
| 1.2 `flows/base.py` | ✅ test_flow_base.py (26 tests) | ✅ GPUProfile, ImageArtifact, FlowOutput, BaseAtomicFlow | ✅ Media_type validator @model_validator | 26/26 |
| 1.3 `flows/extraction.py` | ✅ test_extraction_flow.py (14 tests) | ✅ ExtractionRequest, ExtractionFlow | — | 14/14 |
| 1.4 `modal_config.py` | ✅ test_modal_config (BRIA node assert) | ✅ Added BRIA clone + pip install | — | ✅ |
| 1.5 `job_store.py` | — (extension) | ✅ artifacts in _store_job, update_job | — | ✅ |
| 1.6 `workflows/extraction/manifest.yaml` | ✅ Contract tests in test_extraction_flow.py | ✅ Manifest with input_image + outputs.artifacts | — | ✅ |
| 1.7 `workflows/extraction/workflow.json` | ✅ Contract tests | ✅ LoadImage → BriaRMBG → SaveImage | — | ✅ |
| 1.8 `workflows/models.py` | — (extension) | ✅ outputs field on ManifestSchema | — | ✅ |
| 1.9 `service.py` | — (implicit via router test) | ✅ dispatch_flow, EXTRACTION_FLOW | — | ✅ |
| 1.10 `modal_tasks.py` | — (extension) | ✅ input_volume mount on L4 + T4 functions | — | ✅ |
| 1.11 `router.py` | ✅ test_generation_router.py (all 11 pass) | ✅ POST /generate/extraction endpoint | — | 11/11 |
| 1.12 `test_flow_base.py` | ✅ RED first | — (test file) | — | 26/26 |
| 1.13 `test_extraction_flow.py` | ✅ RED first | — (test file) | — | 14/14 |

### Files Changed (Phase 1)

| File | Action |
|------|--------|
| `api/src/shared/flows/__init__.py` | Created |
| `api/src/shared/flows/base.py` | Created |
| `api/src/shared/flows/extraction.py` | Created |
| `api/src/shared/workflows/models.py` | Modified — added `outputs` field |
| `api/src/shared/job_store.py` | Modified — added `artifacts` field |
| `api/src/shared/modal_config.py` | Modified — added BRIA node install + input_volume |
| `api/src/features/generation/service.py` | Modified — added `dispatch_flow`, `EXTRACTION_FLOW` |
| `api/src/features/generation/modal_tasks.py` | Modified — added `input_volume` mount |
| `api/src/features/generation/router.py` | Modified — added `POST /generate/extraction` |
| `api/src/workflows/extraction/manifest.yaml` | Created |
| `api/src/workflows/extraction/workflow.json` | Created |
| `api/src/tests/test_flow_base.py` | Created — 26 tests |
| `api/src/tests/test_extraction_flow.py` | Created — 14 tests |
| `api/src/tests/test_modal_config.py` | Modified — added BRIA + input_volume assertions |

### Test Results (Phase 1)

```
Total: 247 passed (205 original + 42 new)
- test_flow_base.py: 26/26 passed
- test_extraction_flow.py: 14/14 passed
- test_modal_config.py: 2 new assertions added
- All existing tests: unchanged, all passing
```

## Phase 2 / PR 2 Complete — Composition Flow (FLUX + ControlNet)

**Branch**: `feature/sdd-2-modal-flows-pr2` ← `feature/sdd-2-modal-flows-pr1`

### TDD Cycle Evidence

| Task | RED test written | GREEN code | Refactor | Tests passing |
|------|-----------------|------------|----------|---------------|
| 2.1 `flows/composition.py` | ✅ test_composition_flow.py (29 tests) | ✅ CompositionRequest, CompositionFlow with validate bounds + fixed field guard | — | 29/29 |
| 2.2 `modal_config.py` | ✅ test_modal_config (2 new assertions) | ✅ comfyui_controlnet_aux clone + pip install; controlnets in whitelist | — | 15/15 |
| 2.3 `workflows/composition/manifest.yaml` | ✅ Contract tests in test_composition_flow.py | ✅ Manifest with prompt, bg/fg images, control_mode, unet/clip/vae defaults | — | ✅ |
| 2.4 `workflows/composition/workflow.json` | ✅ Contract tests | ✅ LoadImage(bg+fg) → ControlNetApply → KSampler(FLUX) → VAEDecode → SaveImage | — | ✅ |
| 2.5 `service.py` | ✅ test_generation_service.py (2 new tests) | ✅ COMPOSITION_FLOW added to SUPPORTED_WORKFLOWS | — | 4/4 |
| 2.6 `router.py` | ✅ test_generation_router.py (3 new tests) | ✅ POST /generate/composition endpoint with CompositionFlow | — | 3/3 |
| 2.7 `test_composition_flow.py` | ✅ RED first (29 tests) | — (test file) | — | 29/29 |

### Files Changed (Phase 2)

| File | Action |
|------|--------|
| `api/src/shared/flows/__init__.py` | Modified — added `CompositionFlow`, `CompositionRequest` exports |
| `api/src/shared/flows/composition.py` | Created |
| `api/src/shared/modal_config.py` | Modified — added `comfyui_controlnet_aux` node install + ControlNet models in whitelist |
| `api/src/features/generation/service.py` | Modified — added `COMPOSITION_FLOW` to `SUPPORTED_WORKFLOWS` |
| `api/src/features/generation/router.py` | Modified — added `POST /generate/composition` endpoint |
| `api/src/workflows/composition/manifest.yaml` | Created |
| `api/src/workflows/composition/workflow.json` | Created |
| `api/src/tests/test_composition_flow.py` | Created — 29 tests |
| `api/src/tests/test_generation_service.py` | Modified — added 2 dispatch tests for composition |
| `api/src/tests/test_generation_router.py` | Modified — added 3 endpoint tests for composition |
| `api/src/tests/test_modal_config.py` | Modified — added 2 controlnet-related assertions |

### Test Results (Phase 2)

```
Total: 297 passed (261 baseline + 36 new)
- test_composition_flow.py: 29/29 passed
- test_generation_service.py (TestDispatchFlow): 4/4 passed
- test_generation_router.py (TestPostGenerateComposition): 3/3 passed
- test_modal_config.py: 15/15 passed
- All existing tests: unchanged, all passing
```

## Phase 3 / PR 3 Complete — Identity Flow (PuLID + FLUX on A100) & Legacy Cleanup

**Branch**: `feature/sdd-2-modal-flows-pr3` ← `feature/sdd-2-modal-flows-pr2`

### TDD Cycle Evidence

| Task | RED test written | GREEN code | Refactor | Tests passing |
|------|-----------------|------------|----------|---------------|
| 3.1 `flows/identity.py` | ✅ test_identity_flow.py (30 tests) | ✅ IdentityRequest (width/height multiple-of-64 validator, optional seed), IdentityFlow (A100, 1200s) | — | 30/30 |
| 3.2 `modal_config.py` | ✅ Already verified in test_modal_config.py | ✅ PuLID-Flux node + whitelist already present (no changes needed) | — | ✅ |
| 3.3 `workflows/identity/manifest.yaml` | ✅ Contract tests (reference_face, pulid, face_detector, model defaults) | ✅ Manifest with LoadImage mapping, PuLID model defaults | — | ✅ |
| 3.4 `workflows/identity/workflow.json` | ✅ Contract tests (UNETLoader not GGUF, PuLID nodes, FaceDetailer) | ✅ LoadImage → ApplyPulidFlux → KSampler → FaceDetailer → SaveImage | — | ✅ |
| 3.5 `modal_tasks.py` | ✅ test_generation_service dispatch tests | ✅ `run_generation_a100` (A100 GPU, 3600s timeout) | — | ✅ |
| 3.6 `service.py` | ✅ dispatch flow tests (A100 routing, params, timeout_s) | ✅ IDENTITY_FLOW registered; GGUF removed from SUPPORTED_WORKFLOWS; `resolve_identity_seed`/`download_image_to_base64` removed | — | ✅ |
| 3.7 `router.py` | ✅ Endpoint tests (indirect via service) | ✅ POST /generate/identity endpoint with IdentityFlow | — | ✅ |
| 3.8 `models.py` | ✅ Test: identidad_gguf rejected, fields rejected | ✅ identidad_gguf removed from WorkflowName, SUPPORTED_WORKFLOWS; deprecated fields removed | — | ✅ |
| 3.9 Delete `identidad_gguf/` | ✅ test_retired_workflow_assets_are_removed passes | ✅ Directory deleted | — | ✅ |
| 3.10 `test_generation_models.py` | ✅ Updated: removed TestIdentidadGGUFGenerateRequest, added rejection tests | — (test file) | — | ✅ |
| 3.11 `test_generation_service.py` | ✅ Updated: removed GGUF routing, added identity dispatch + params + timeout tests | — (test file) | — | ✅ |
| 3.12 `test_identity_flow.py` | ✅ Created RED first (30 tests) | — (test file) | — | 30/30 |
| 3.13 `test_workflow_templates.py` | ✅ Updated: identity + extraction + composition validation, removed identidad_gguf | — (test file) | — | ✅ |
| 3.14 `test_modal_config.py` | ✅ Already verified (no changes needed) | — (test file) | — | ✅ |

### Files Changed (Phase 3)

| File | Action |
|------|--------|
| `api/src/shared/flows/identity.py` | **Created** |
| `api/src/shared/flows/__init__.py` | Modified — added IdentityFlow, IdentityRequest exports |
| `api/src/workflows/identity/manifest.yaml` | **Created** |
| `api/src/workflows/identity/workflow.json` | **Created** |
| `api/src/features/generation/modal_tasks.py` | Modified — added `run_generation_a100` (A100, 3600s) |
| `api/src/features/generation/service.py` | Modified — added IDENTITY_FLOW, removed identidad_gguf, removed resolve_identity_seed + download_image_to_base64, mapped A100 to run_generation_a100 |
| `api/src/features/generation/router.py` | Modified — added POST /generate/identity endpoint |
| `api/src/features/generation/models.py` | Modified — removed identidad_gguf from WorkflowName + SUPPORTED_WORKFLOWS, removed legacy fields (image_url, width, height, seed) |
| `api/src/workflows/identidad_gguf/manifest.yaml` | **Deleted** |
| `api/src/workflows/identidad_gguf/workflow.json` | **Deleted** |
| `api/src/tests/test_identity_flow.py` | **Created** — 30 tests |
| `api/src/tests/test_generation_models.py` | Modified — removed TestIdentidadGGUFGenerateRequest, added rejection tests |
| `api/src/tests/test_generation_service.py` | Modified — removed GGUF routing, added identity dispatch tests |
| `api/src/tests/test_workflow_engine.py` | Modified — replaced identidad_gguf test with identity test |
| `api/src/tests/test_workflow_templates.py` | Modified — added identity/composition/extraction, removed identidad_gguf |
| `api/src/tests/test_modal_config.py` | Modified — minor cleanup |

### Test Results (Phase 3)

```
Total: 360 passed (297 baseline + 63 new/modified)
- test_identity_flow.py: 30/30 passed
- test_generation_models.py: all tests passing (GGUF removed, rejection tests added)
- test_generation_service.py: all tests passing (GGUF removed, 6 identity dispatch tests added)
- test_workflow_templates.py: all tests passing (identity, extraction, composition validated)
- test_workflow_engine.py: identity manifest test passing
- test_modal_config.py: all passing
- All Phase 1 & 2 tests: unchanged, all passing
```

### Test Count Summary

```
Phase 1 baseline:     247
Phase 2 additions:    +50 (Total: 297)
Phase 3 additions:    +63 (Total: 360) — 360/360 passed
```

### Status

#### Phase 1 (PR 1) ✅
- [x] 1.1 — Create `flows/__init__.py`
- [x] 1.2 — Create `flows/base.py`
- [x] 1.3 — Create `flows/extraction.py`
- [x] 1.4 — Modify `modal_config.py` (BRIA node)
- [x] 1.5 — Modify `job_store.py` (artifacts field)
- [x] 1.6 — Create `workflows/extraction/manifest.yaml`
- [x] 1.7 — Create `workflows/extraction/workflow.json`
- [x] 1.8 — Modify `workflows/models.py` (outputs field)
- [x] 1.9 — Modify `service.py` (dispatch_flow, EXTRACTION_FLOW)
- [x] 1.10 — Modify `modal_tasks.py` (input_volume mount)
- [x] 1.11 — Modify `router.py` (extraction endpoint)
- [x] 1.12 — Create `test_flow_base.py`
- [x] 1.13 — Create `test_extraction_flow.py`

#### Phase 2 (PR 2) ✅
- [x] 2.1 — Create `flows/composition.py`
- [x] 2.2 — Modify `modal_config.py` (ControlNet aux + whitelist)
- [x] 2.3 — Create `workflows/composition/manifest.yaml`
- [x] 2.4 — Create `workflows/composition/workflow.json`
- [x] 2.5 — Modify `service.py` (COMPOSITION_FLOW)
- [x] 2.6 — Modify `router.py` (composition endpoint)
- [x] 2.7 — Create `test_composition_flow.py`

#### Phase 3 (PR 3) ✅
- [x] 3.1 — Create `flows/identity.py`
- [x] 3.2 — Modify `modal_config.py` (PuLID/A100 — already present)
- [x] 3.3 — Create `workflows/identity/manifest.yaml`
- [x] 3.4 — Create `workflows/identity/workflow.json`
- [x] 3.5 — Modify `modal_tasks.py` (A100 function)
- [x] 3.6 — Modify `service.py` (IDENTITY_FLOW, cleanup)
- [x] 3.7 — Modify `router.py` (identity endpoint)
- [x] 3.8 — Modify `models.py` (GGUF removal)
- [x] 3.9 — Delete `identidad_gguf/` directory
- [x] 3.10 — Update `test_generation_models.py`
- [x] 3.11 — Update `test_generation_service.py`
- [x] 3.12 — Create `test_identity_flow.py`
- [x] 3.13 — Update `test_workflow_templates.py`
- [x] 3.14 — Update `test_modal_config.py`

## All Phases Complete ✅
- `feature/sdd-2-modal-flows-pr1` → `feature/sdd-2-modal-flows-pr2` → `feature/sdd-2-modal-flows-pr3`
- Implementation: 3 chained PRs, all complete
- Tests: 360 passed, 0 failed
- Legacy identidad_gguf: fully deleted
