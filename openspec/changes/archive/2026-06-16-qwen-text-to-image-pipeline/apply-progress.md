# Apply Progress: Qwen Text-to-Image Pipeline

## Status

All implementation tasks are complete under maintainer-approved `size:exception` single-PR delivery.

## Completed Tasks

- [x] 1.1 Add `validate_dimensions()` helper
- [x] 1.2 Create Qwen `workflow.json`
- [x] 1.3 Create Qwen `manifest.yaml`
- [x] 1.4 Write dimension validator unit tests
- [x] 2.1 Extend `WorkflowName` with `qwen_txt2img`
- [x] 2.2 Add Qwen request fields and validation
- [x] 2.3 Implement Qwen quality-mode defaults
- [x] 2.4 Implement Lightning LoRA injection
- [x] 3.1 Wire router fields into service enqueue
- [x] 4.1 Test quality mode defaults
- [x] 4.2 Test Lightning LoRA injection
- [x] 4.3 Test Qwen manifest references
- [x] 4.4 Test full POST `/generate` Qwen request path with mocked service dispatch
- [x] 4.5 Test missing Qwen model whitelist/cache failure boundary
- [x] 5.1 Update default `ALLOWED_MODELS_JSON` with Qwen model filenames

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_workflow_models.py` | Unit | ✅ 153/153 relevant baseline | ✅ Import failed for missing `validate_dimensions` | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Valid dimensions, range errors, alignment errors, pixel budget | ✅ Constants extracted |
| 1.2 | `api/src/tests/test_workflow_templates.py` | Unit | N/A (new files) | ✅ Qwen workflow file missing | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Node class set and no custom switch/primitive nodes | ➖ None needed |
| 1.3 | `api/src/tests/test_workflow_templates.py` | Unit | N/A (new files) | ✅ Qwen manifest file missing | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Defaults, runtime mappings, engine resolution | ✅ Engine allows non-mapped manifest metadata defaults |
| 1.4 | `api/src/tests/test_workflow_models.py` | Unit | ✅ 153/153 relevant baseline | ✅ Tests written before helper | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Multiple valid and invalid cases | ➖ None needed |
| 2.1 | `api/src/tests/test_generation_models.py` | Unit | ✅ 153/153 relevant baseline | ✅ `qwen_txt2img` rejected by Literal | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Alias and workflow_name paths | ➖ None needed |
| 2.2 | `api/src/tests/test_generation_models.py` | Unit | ✅ 153/153 relevant baseline | ✅ Width/height/quality fields missing | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Fast/high, invalid dimensions, non-Qwen scoping | ✅ Reused shared dimension helper |
| 2.3 | `api/src/tests/test_generation_service.py` | Unit | ✅ 153/153 relevant baseline | ✅ Missing `resolve_qwen_quality_defaults` import | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Fast and high quality tables | ✅ Extracted Qwen constants |
| 2.4 | `api/src/tests/test_generation_service.py` | Unit | ✅ 153/153 relevant baseline | ✅ Fast mode had no LoRA injection behavior | ✅ Relevant suite 176/176, full suite 284/284 | ✅ LoRA node presence plus sampler redirection | ✅ Extracted injection helper |
| 3.1 | `api/src/tests/test_generation_router.py` | Integration | ✅ 153/153 relevant baseline | ✅ Router did not forward Qwen controls | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Workflow plus three forwarded controls | ➖ None needed |
| 4.1 | `api/src/tests/test_generation_service.py` | Unit | ✅ 153/153 relevant baseline | ✅ Missing quality defaults resolver | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Fast and high cases | ➖ None needed |
| 4.2 | `api/src/tests/test_generation_service.py` | Unit | ✅ 153/153 relevant baseline | ✅ Missing LoRA graph mutation | ✅ Relevant suite 176/176, full suite 284/284 | ✅ LoRA cache call and KSampler model link | ➖ None needed |
| 4.3 | `api/src/tests/test_workflow_templates.py` | Unit | ✅ 153/153 relevant baseline | ✅ Qwen manifest/template absent | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Engine load and runtime parameter application | ✅ Metadata defaults preserved without graph mapping |
| 4.4 | `api/src/tests/test_generation_router.py`, `api/src/tests/test_generation_service.py` | Integration | ✅ 153/153 relevant baseline | ✅ Qwen request path unsupported | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Router forwarding plus service resolved graph assertions | ➖ None needed |
| 4.5 | `api/src/tests/test_generation_service.py` | Unit | ✅ 153/153 relevant baseline | ✅ Qwen model categories unsupported | ✅ Relevant suite 176/176, full suite 284/284 | ✅ Allowed/cached models and missing whitelist failure | ✅ Validate all models before cache resolution |
| 5.1 | `api/src/tests/test_generation_service.py`, `api/src/tests/test_workflow_templates.py` | Unit | ✅ 153/153 relevant baseline | ✅ Qwen model filenames absent from whitelist support | ✅ Relevant suite 176/176, full suite 284/284 | ✅ UNET/CLIP/VAE/LoRA whitelist categories exercised | ✅ Extended whitelist loader categories |

## Test Summary

- **Total tests written**: 23
- **Total tests passing**: 284
- **Layers used**: Unit (22), Integration (1)
- **Approval tests**: None — no refactoring-only tasks
- **Pure functions created**: 3 (`validate_dimensions`, `resolve_qwen_quality_defaults`, `inject_qwen_lightning_lora`)

## Commands Run

- `python3 -m pytest src/tests/test_workflow_models.py src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_workflow_engine.py src/tests/test_workflow_templates.py` → 153 passed (safety net)
- `python3 -m pytest src/tests/test_workflow_models.py src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_workflow_templates.py` → RED: 2 collection errors for missing production symbols
- `python3 -m pytest src/tests/test_generation_service.py` → 44 passed after cache-order fix
- `python3 -m pytest src/tests/test_workflow_models.py src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_workflow_templates.py src/tests/test_workflow_engine.py` → 176 passed
- `python3 -m pytest` → 284 passed

## Deviations / Notes

- `quality_mode` is stored as manifest metadata under `defaults` and resolved in the service before `WorkflowEngine.execute()`. The engine now ignores non-mapped defaults while still rejecting undeclared runtime parameters, allowing quality metadata without adding dummy ComfyUI nodes.
- Qwen model whitelist/cache support was extended to `unets`, `clip`, and `vae` categories so missing Qwen model files fail before Modal GPU spawn.
