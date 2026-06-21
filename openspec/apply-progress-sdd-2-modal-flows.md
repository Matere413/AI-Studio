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

### Files Changed

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

### Test Results

```
Total: 247 passed (205 original + 42 new)
- test_flow_base.py: 26/26 passed
- test_extraction_flow.py: 14/14 passed
- test_modal_config.py: 2 new assertions added
- All existing tests: unchanged, all passing
```

### Status

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

Phase 2 & 3: Not started (blocked — wait for PR 1 review & merge)
