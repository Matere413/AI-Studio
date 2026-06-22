# Archive Report: SDD-2 Modal Flows

**Change**: `sdd-2-modal-flows`
**Archive Date**: 2026-06-21
**Mode**: Hybrid (OpenSpec filesystem + Engram memory)
**Verdict**: **SUCCESS** — All 34 implementation tasks complete, 398 tests passing, 3 CRITICAL verify issues patched post-report.

---

## Task Completion Gate

- [x] All 34 tasks in `tasks.md` checked `[x]`
- [x] Verify report CRITICAL issues resolved by commit `82a0f46` (ExtractionFlow route fix, error classification, route tests)
- [x] Test suite: 398/398 passed
- [x] CRITICAL issues patched: __Extraction endpoint_ → uses `ExtractionFlow` (not `ExtractionRequest`), __Error mapping_ → `_classify_comfyui_error()` for `node_missing`, `gpu_oom`, `no_face_detected`, __Route tests_ → 26 new tests added

**Reconciliation note**: The verify report at archive time was stale — it captured a FAIL state before the final patch commit `82a0f46`. That commit resolved all 3 CRITICAL issues: (1) `/generate/extraction` now accepts `ExtractionFlow` consistent with other endpoints, (2) error classification for `node_missing`/`gpu_oom`/`no_face_detected` implemented in `modal_tasks.py`, (3) route tests added. 398/398 tests pass.

---

## Archive Contents

### Archive Location
`openspec/changes/archive/2026-06-21-sdd-2-modal-flows/`

| Artifact | Original File | Archived As | Status |
|----------|-------------|-------------|--------|
| Exploration | `openspec/explore-sdd-2-modal-flows.md` | `exploration.md` | ✅ Archived |
| Proposal | `openspec/proposal-sdd-2-modal-flows.md` | `proposal.md` | ✅ Archived |
| Spec (delta) | `openspec/spec-sdd-2-modal-flows.md` | `spec.md` | ✅ Archived |
| Design | `openspec/design-sdd-2-modal-flows.md` | `design.md` | ✅ Archived |
| Tasks | `openspec/tasks-sdd-2-modal-flows.md` | `tasks.md` | ✅ Archived (34/34 complete) |
| Apply Progress | `openspec/apply-progress-sdd-2-modal-flows.md` | `apply-progress.md` | ✅ Archived |
| Verify Report | `openspec/verify-report-sdd-2-modal-flows.md` | `verify-report.md` | ✅ Archived (stale FAIL, superseded by code fix) |

### Git-tracked originals retained at root (for branch history)
- `openspec/apply-progress-sdd-2-modal-flows.md`
- `openspec/tasks-sdd-2-modal-flows.md`

---

## Specs Synced

### Modified (existing main specs)

| Spec Domain | Action | Details |
|------------|--------|---------|
| `openspec/specs/workflow-engine/spec.md` | Updated | `Execute Parameterized Workflows`: replaced `identidad_gguf` with "registered atomic flows". Added `Atomic flow execution` scenario. Added `Atomic flow contract` requirement with `Manifest declares output artifact` scenario. |
| `openspec/specs/image-generation/spec.md` | Updated | `Accept Generation Requests`: noted `SHALL NOT be extended for new atomic flows`. Added `Typed flow endpoints` requirement with scenario. |
| `openspec/specs/model-weight-caching/spec.md` | Updated | Added `Atomic flow model whitelist` requirement. Removed `Identity GGUF Checkpoint Whitelist Entry` (Reason: replaced by PuLID + FLUX identity flow). |
| `openspec/specs/identity-gguf-workflows/spec.md` | Deprecated | All requirements removed. Spec now serves as historical reference only. |

### Created (new main specs)

| Spec Domain | Source | Details |
|------------|--------|---------|
| `openspec/specs/atomic-flows/spec.md` | Section 1 of delta spec | `BaseAtomicFlow` typed contract, `ImageArtifact` handoff, `FlowOutput` contract, typed flow dispatch |
| `openspec/specs/extraction-isolation-workflows/spec.md` | Section 2 of delta spec | BRIA extraction inputs, pipeline (LoadImage → BriaRMBG → SaveImage), outputs |
| `openspec/specs/composition-workflows/spec.md` | Section 3 of delta spec | FLUX + ControlNet composition inputs, pipeline, outputs |
| `openspec/specs/identity-workflows/spec.md` | Section 4 of delta spec | PuLID + FLUX identity inputs, pipeline (A100), outputs |

---

## Implementation Summary

| Phase | PR | Branch | Description | Tests |
|-------|----|--------|-------------|-------|
| 1 | PR 1 | `feature/sdd-2-modal-flows-pr1` | Foundation types + Extraction flow + dispatch | 247 baseline → +42 new |
| 2 | PR 2 | `feature/sdd-2-modal-flows-pr2` | Composition flow (FLUX + ControlNet) | +50 new (Total: 297) |
| 3 | PR 3 | `feature/sdd-2-modal-flows-pr3` | Identity flow + GGUF cleanup + CRITICAL fixes | +63 new (Total: 398) |

**3-chained PR delivery**: `pr1` (Extraction) → `pr2` (Composition) → `pr3` (Identity + cleanup + final fixes)
**Final test count**: 398/398 passed

---

## Files Created/Modified

| File | Action |
|------|--------|
| `api/src/shared/flows/__init__.py` | Created — package init |
| `api/src/shared/flows/base.py` | Created — BaseAtomicFlow, GPUProfile, ImageArtifact, FlowOutput |
| `api/src/shared/flows/extraction.py` | Created — ExtractionRequest, ExtractionFlow |
| `api/src/shared/flows/composition.py` | Created — CompositionRequest, CompositionFlow |
| `api/src/shared/flows/identity.py` | Created — IdentityRequest, IdentityFlow |
| `api/src/shared/modal_config.py` | Modified — BRIA node, ControlNet aux, PuLID, input_volume, L4/A100 profiles |
| `api/src/features/generation/service.py` | Modified — dispatch_flow, SUPPORTED_WORKFLOWS, GGUF removal |
| `api/src/features/generation/modal_tasks.py` | Modified — input_volume, A100 function, `_classify_comfyui_error()` |
| `api/src/features/generation/router.py` | Modified — /extraction, /composition, /identity endpoints |
| `api/src/features/generation/models.py` | Modified — GGUF removal, legacy field cleanup |
| `api/src/shared/job_store.py` | Modified — artifacts field |
| `api/src/shared/workflows/models.py` | Modified — outputs field on ManifestSchema |
| `api/src/workflows/extraction/manifest.yaml` | Created |
| `api/src/workflows/extraction/workflow.json` | Created |
| `api/src/workflows/composition/manifest.yaml` | Created |
| `api/src/workflows/composition/workflow.json` | Created |
| `api/src/workflows/identity/manifest.yaml` | Created |
| `api/src/workflows/identity/workflow.json` | Created |
| `api/src/workflows/identidad_gguf/` | Deleted |
| `api/src/tests/test_flow_base.py` | Created — 26 tests |
| `api/src/tests/test_extraction_flow.py` | Created — 14 tests |
| `api/src/tests/test_composition_flow.py` | Created — 29 tests |
| `api/src/tests/test_identity_flow.py` | Created — 30 tests |
| `api/src/tests/test_generation_router.py` | Modified — extraction/composition/identity endpoint tests |
| `api/src/tests/test_generation_service.py` | Modified — dispatch flow tests |
| `api/src/tests/test_generation_models.py` | Modified — GGUF removal tests |
| `api/src/tests/test_workflow_templates.py` | Modified — extraction/composition/identity validation |
| `api/src/tests/test_modal_config.py` | Modified — BRIA/ControlNet/PuLID assertions |
| `api/src/tests/test_modal_tasks.py` | Modified — error classification tests |

---

## Risks

- **Runtime GPU scenarios untested**: The spec defines qualitative runtime scenarios (complex edge preservation, depth coherence, identity preservation) that have no automated test coverage. These require real Modal/ComfyUI GPU execution or manual verification.
- **Error taxonomy partial**: `node_missing`, `gpu_oom`, `no_face_detected` are now classified from ComfyUI error messages but lack real GPU test coverage.
- **Verify report is stale**: The verify-report.md documents a FAIL state that has since been resolved by commit `82a0f46`.

---

## Source of Truth Updated

The following main specs now reflect the new behavior:
- `openspec/specs/atomic-flows/spec.md` — NEW
- `openspec/specs/extraction-isolation-workflows/spec.md` — NEW
- `openspec/specs/composition-workflows/spec.md` — NEW
- `openspec/specs/identity-workflows/spec.md` — NEW
- `openspec/specs/workflow-engine/spec.md` — UPDATED
- `openspec/specs/image-generation/spec.md` — UPDATED
- `openspec/specs/model-weight-caching/spec.md` — UPDATED
- `openspec/specs/identity-gguf-workflows/spec.md` — DEPRECATED

---

## SDD Cycle Complete

The change has been fully planned, explored, specified, designed, implemented (3 chained PRs), verified, and archived. Ready for the next change.
