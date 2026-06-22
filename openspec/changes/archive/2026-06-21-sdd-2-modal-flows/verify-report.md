# Verification Report: SDD-2 Modal Flows

**Change**: `sdd-2-modal-flows`  
**Branch**: `feature/sdd-2-modal-flows-pr3`  
**Mode**: Strict TDD  
**Persistence**: openspec file  
**Verdict**: **FAIL**

The full API test suite passes, and most static implementation evidence matches the Extraction, Composition, Identity, and GGUF cleanup tasks. However, verification found blocking gaps against the spec: the extraction endpoint does not accept the client-facing typed payload without fixed server fields, and several required runtime/error scenarios are either unimplemented or untested (`node_missing`, `gpu_oom`, `no_face_detected`, qualitative GPU output behavior). Under Strict TDD, a required scenario without a passing covering runtime test remains non-compliant.

---

## Completeness

| Metric | Value |
|--------|-------|
| Phases | 3/3 present |
| Tasks total | 34 |
| Tasks checked complete in tasks artifact | 34 |
| Tasks incomplete in tasks artifact | 0 |
| Spec dimensions reviewed | Extraction, Composition, Identity, GGUF cleanup |
| Design reviewed | Yes — `openspec/design-sdd-2-modal-flows.md` |
| Apply progress reviewed | Yes — `openspec/apply-progress-sdd-2-modal-flows.md` |

---

## Build & Tests Execution

### Build

No separate build command is defined for `api/`; verification used the configured runner: `pytest`.

### Tests

**Command**: `pytest` from `api/`  
**Result**: ✅ 372 passed, 0 failed, 0 skipped  
**Runtime**: 20.51s

```text
platform darwin -- Python 3.14.6, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/matere/Documents/Proyectos Programados/AI-Studio/api
plugins: asyncio-1.4.0, anyio-4.13.0
collected 372 items
...
============================= 372 passed in 20.51s =============================
```

### Additional Verification Commands

| Command | Result | Evidence |
|---------|--------|----------|
| `pytest --collect-only -q` | ✅ 372 collected | Confirms all test nodes are discoverable. |
| Extraction endpoint payload without fixed fields | ❌ 422 | `POST /generate/extraction` with only `prompt` + `input_image` returns missing `workflow_name`, `gpu_profile`, `timeout_s`. |
| Extraction endpoint payload with fixed fields | ✅ 202 | Same endpoint succeeds only when client sends `workflow_name="extraction"`, `gpu_profile="L4"`, `timeout_s=300`. |
| Optional quality tool probe | ➖ unavailable | `pytest_cov=False`, `ruff=False`, `mypy=False`. |

### Coverage

Coverage analysis skipped — no coverage tool detected (`pytest-cov` is not installed and `requirements-dev.txt` only lists `pytest`, `pytest-asyncio`, `httpx`, `websockets`).

---

## TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD evidence reported | ✅ | Apply progress contains TDD Cycle Evidence tables for Phases 1–3. |
| RED confirmed: test files exist | ⚠️ | Core files exist; several rows are marked as extension/no-change/indirect rather than explicit RED tests. |
| GREEN confirmed | ✅ | Full suite passes: 372/372. |
| Triangulation adequate | ⚠️ | Model, route, manifest, and dispatch cases are triangulated; qualitative runtime scenarios are not. |
| Safety net for modified files | ⚠️ | Existing suite passes, but apply artifact does not report explicit safety-net evidence for every modified extension task. |
| Assertion quality audit | ✅ | No tautologies or critical meaningless assertions found in SDD-related tests. Some smoke guards (`is not None`) are accompanied by substantive assertions. |

**TDD compliance**: Passes execution, but fails full Strict TDD scenario compliance because required spec scenarios lack covering runtime tests.

---

## Test Layer Distribution

| Layer | Tests | Files | Notes |
|-------|-------|-------|-------|
| Unit / contract | 331 | 16 | Pydantic models, service dispatch, workflow manifests, Modal helpers, cache contracts. |
| Integration / API | 41 | 3 | FastAPI/TestClient route and websocket behavior; includes mocked Modal spawns. |
| Real GPU / external E2E | 0 | 0 | No real Modal/ComfyUI GPU execution observed. |
| **Total** | **372** | **19** | Full suite passed. |

---

## Spec Compliance Matrix

| Requirement | Scenario | Covering Evidence | Result |
|-------------|----------|-------------------|--------|
| BaseAtomicFlow typed contract | Valid flow subclass registers/exposed | `test_extraction_flow.py`, `test_composition_flow.py`, `test_identity_flow.py`, `test_workflow_templates.py`; `service.SUPPORTED_WORKFLOWS` includes all three flows | ✅ COMPLIANT |
| BaseAtomicFlow typed contract | Missing `workflow_name` rejected | `test_flow_base.py::TestBaseAtomicFlow::test_missing_workflow_name_rejected` | ✅ COMPLIANT |
| BaseAtomicFlow typed contract | Prompt length enforced | `test_flow_base.py::test_prompt_too_long_rejected`; `test_generation_models.py` prompt length tests | ✅ COMPLIANT |
| ImageArtifact handoff | Prior flow output feeds next flow by `volume_path` | `test_generation_service.py::TestValidateArtifactOwnership::test_accepts_artifact_with_valid_source_job_id` | ✅ COMPLIANT |
| ImageArtifact handoff | Artifact path escape rejected | `test_flow_base.py` traversal + absolute path tests; API identity invalid path test | ✅ COMPLIANT |
| ImageArtifact handoff | Unsupported media type rejected | `test_flow_base.py`, `test_extraction_flow.py`, `test_identity_flow.py` | ✅ COMPLIANT |
| FlowOutput contract | Successful flow returns artifacts | `test_flow_base.py::TestFlowOutput`, `test_modal_tasks.py::test_happy_path_stores_artifacts_from_manifest_config` | ✅ COMPLIANT |
| Typed flow dispatch | Typed request accepted | Composition and identity route tests pass; extraction endpoint fails client-facing typed payload without fixed fields | ❌ FAILING |
| Typed flow dispatch | Monolithic field rejected | `extra="forbid"` tests in flow models and identity route extra-field test | ✅ COMPLIANT |
| Extraction inputs | Valid source image produces transparent PNG artifact | Manifest declares `extracted_image`, `image/png`, `has_alpha`; no real BRIA runtime execution | ⚠️ PARTIAL |
| Extraction inputs | Missing source rejected | `test_extraction_flow.py::test_missing_input_image_rejected` | ✅ COMPLIANT |
| Extraction inputs | Invalid source media type rejected | `test_extraction_flow.py::test_invalid_source_media_type_rejected` | ✅ COMPLIANT |
| Extraction pipeline | LoadImage → BriaRMBG → SaveImage | `api/src/workflows/extraction/workflow.json`; `test_extraction_flow.py` workflow asset tests | ✅ COMPLIANT |
| Extraction pipeline | Complex edges handled | No runtime BRIA quality test with fine hair/fur/busy background | ❌ UNTESTED |
| Extraction pipeline | Missing BRIA node fails fast with `node_missing` | No code/test maps missing custom node to `node_missing`; generic ComfyUI failures map to `comfyui_execution_failed` | ❌ UNTESTED / NOT IMPLEMENTED |
| Extraction outputs | Manifest declares `extracted_image`, `image/png`, `has_alpha=true` | `test_extraction_flow.py::test_output_artifact_has_correct_media_type` | ✅ COMPLIANT |
| Composition inputs | Extraction output feeds composition | `TestValidateArtifactOwnership::test_accepts_artifact_with_valid_source_job_id`; params map artifact to `volume_path` | ✅ COMPLIANT |
| Composition inputs | Explicit upload feeds composition | Input paths starting with `input/` accepted; composition route tests pass for explicit foreground/background images | ✅ COMPLIANT |
| Composition inputs | Invalid `control_mode` rejected | `test_composition_flow.py`, `test_generation_router.py` | ✅ COMPLIANT |
| Composition pipeline | FLUX + ControlNet graph structure | `test_composition_flow.py` validates LoadImage, ControlNetLoader/Apply, preprocessors, VAEEncode, KSampler, VAEDecode, SaveImage | ✅ COMPLIANT |
| Composition pipeline | Depth mode coherent scene | No real image generation/depth coherence test | ❌ UNTESTED |
| Composition pipeline | ControlNet model missing fails fast with `model_not_cached` | Model cache tests + router/service handling for `ModelNotCachedError` | ✅ COMPLIANT |
| Composition pipeline | VRAM pressure returns `gpu_oom`, no auto retry | No OOM classification code/test; generic exceptions map to `comfyui_execution_failed` | ❌ UNTESTED / NOT IMPLEMENTED |
| Composition outputs | Composed image artifact `image/png` | Manifest declares `composed_image`, `image/png`; dispatch passes output artifacts to Modal task | ✅ COMPLIANT |
| Identity inputs | Valid identity request | `test_identity_flow.py`, `test_generation_router.py::TestPostGenerateIdentity` | ✅ COMPLIANT |
| Identity inputs | Non-face reference rejected with `no_face_detected` | Face detector model is present, but no explicit no-face test or error-code mapping exists | ❌ UNTESTED / NOT IMPLEMENTED |
| Identity inputs | Invalid resolution rejected | `test_identity_flow.py`, `test_generation_router.py` multiple-of-64 tests | ✅ COMPLIANT |
| Identity pipeline | PuLID + FLUX graph structure | `test_identity_flow.py` validates PuLID nodes, UNETLoader, KSampler, VAEDecode, FaceDetailer, SaveImage | ✅ COMPLIANT |
| Identity pipeline | Identity preserved across prompts | No real identity similarity/runtime test | ❌ UNTESTED |
| Identity pipeline | PuLID model not whitelisted rejected | `GenerationService.validate_models` + model whitelist/service tests | ✅ COMPLIANT |
| Identity pipeline | Missing PuLID node fails fast with `node_missing` | No explicit missing-node detection or `node_missing` mapping | ❌ UNTESTED / NOT IMPLEMENTED |
| Identity output | Output artifact `image/png`; dimensions multiples of 64 | Manifest output + identity width/height validation tests | ✅ COMPLIANT |
| Workflow engine delta | Manifest declares output artifact metadata | `ManifestSchema.outputs` + flow manifest tests | ✅ COMPLIANT |
| Workflow engine delta | Atomic flow execution resolves inputs and maps artifacts | `GenerationService.dispatch_flow` tests + Modal artifact persistence test | ✅ COMPLIANT |
| Image generation delta | `/generate/extraction`, `/composition`, `/identity` return 202 | Composition/identity pass; extraction fails without client-supplied fixed fields and has no route test | ❌ FAILING |
| Legacy GenerateRequest delta | Do not extend monolithic request for new flows | `GenerateRequest` supports only `flux2_txt2img` and `flux2_editing`; new flows use flow models | ✅ COMPLIANT |
| Model weight caching delta | Atomic flow models whitelisted | `modal_config.default_whitelist`, `test_modal_config.py`, `test_workflow_templates.py` | ✅ COMPLIANT |
| GGUF cleanup | Remove legacy GGUF workflow assets and whitelist | `identidad_gguf/` absent; `test_workflow_templates.py`, `test_generation_models.py`, `test_modal_config.py` | ✅ COMPLIANT |

**Compliance summary**: 30 compliant, 2 partial/failing endpoint-related, 7 untested/not implemented required scenarios.  
Because Strict TDD requires passing covering tests for spec scenarios, this change is not archive-ready.

---

## Correctness (Static Evidence)

| Area | Status | Notes |
|------|--------|-------|
| Base flow types | ✅ Implemented | `BaseAtomicFlow`, `GPUProfile`, `ImageArtifact`, `FlowOutput` in `api/src/shared/flows/base.py`. |
| Extraction | ⚠️ Partial | Flow model, workflow, manifest, dispatch exist; route uses `ExtractionRequest` instead of `ExtractionFlow`, requiring client-supplied server-fixed fields. |
| Composition | ✅ Implemented | Flow model defaults to L4/600s; ControlNet depth/canny mapping; route and dispatch tests pass. |
| Identity | ✅ Implemented with runtime caveats | Flow model defaults to A100/1200s; PuLID + FLUX graph and route tests pass; no no-face/identity-similarity runtime verification. |
| GGUF cleanup | ✅ Implemented | Legacy workflow removed from models, service support, workflow assets, and Modal config tests. |
| Output artifacts | ✅ Implemented | Manifest outputs and Modal job artifact persistence are present. |
| Error taxonomy | ❌ Incomplete | `node_missing`, `gpu_oom`, and `no_face_detected` are required by spec but not explicitly implemented/tested. |

---

## Coherence (Design)

| Design Decision | Followed? | Notes |
|-----------------|-----------|-------|
| Typed flow modules in `src/shared/flows/` | ✅ Yes | Base + extraction/composition/identity modules exist. |
| Keep `workflow.json` + `manifest.yaml` as source of truth | ✅ Yes | Each atomic flow has both assets and contract tests. |
| Use native `LoadImage` with `/root/ComfyUI/input` volume | ✅ Yes | Modal tasks mount `input_volume`; flow manifests map image artifacts to `LoadImage`. |
| Per-profile Modal functions | ✅ Yes | T4, L4, and A100 functions exist; dispatch maps GPU profile. |
| Remove `identidad_gguf` after identity flow | ✅ Yes | Removed from supported legacy API and workflow assets. |
| Runtime error classification for required scenarios | ❌ No | Design/spec error codes are not fully represented in Modal execution error mapping. |

---

## Issues Found

### CRITICAL

1. **Extraction endpoint rejects the natural typed payload.**  
   Evidence: `POST /generate/extraction` with `prompt` + `input_image` returns `422` requiring `workflow_name`, `gpu_profile`, and `timeout_s`. Composition and identity routes use concrete flow classes with fixed defaults; extraction uses `ExtractionRequest` and has no route test. This violates the typed endpoint scenario and makes `/generate/extraction` inconsistent.

2. **Required runtime error codes are not implemented/tested.**  
   `node_missing` for missing BRIA/PuLID nodes, `gpu_oom` for VRAM pressure, and `no_face_detected` for invalid identity references are required scenarios. Current Modal execution maps generic exceptions to `comfyui_execution_failed`.

3. **Required qualitative runtime scenarios have no passing runtime evidence.**  
   Complex BRIA edge preservation, depth scene coherence, and identity preservation across prompts are not covered by real ComfyUI/Modal/GPU tests or a documented manual verification allowance.

### WARNING

1. Strict TDD apply evidence has several indirect/no-change rows rather than explicit RED evidence per task, even though the current full suite passes.
2. Coverage, linter, and type-checker evidence is unavailable because the tools are not installed.
3. The full suite reports 372 tests now, while apply progress says 360; this is positive growth but the apply artifact is stale on count.

### SUGGESTION

1. Add route-level tests for `/generate/extraction` mirroring composition and identity.
2. Add explicit error-code mapping tests for ComfyUI missing-node, OOM, and no-face failures before archive.
3. Add a separate manual/GPU verification artifact if real Modal/ComfyUI tests remain outside automated CI.

---

## Final Verdict

**FAIL** — The implementation is largely present and the automated suite is green, but Strict TDD/spec verification blocks archive readiness due to one failing typed endpoint scenario and multiple untested/unimplemented required runtime scenarios.
