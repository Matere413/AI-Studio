# Tasks: Premium Product Image Workflows

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~490 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Workflow manifest + engine support | PR 1 | base = feature/tracker branch; workflow.json, manifest, models/engine changes, tests |
| 2 | Generation API + modal gate | PR 2 | base = PR 1 branch; request fields, service normalization, whitelist, tests |
| 3 | Frontend controls | PR 3 | base = PR 2 branch; store types, API payload, Sidebar chip + toggle, tests |

## Phase 1: Foundation — Workflow Assets + Engine

- [x] 1.1 RED: Write test in `test_workflow_models.py` for manifest schema with format enum/dims
- [x] 1.2 GREEN: Create `api/src/workflows/product_premium/workflow.json` — premium ComfyUI graph
- [x] 1.3 Create `api/src/workflows/product_premium/manifest.yaml` — format dims, checkpoint, prompt
- [x] 1.4 Extend `api/src/shared/workflows/models.py` — add product format metadata to manifest model
- [x] 1.5 Extend `api/src/shared/workflows/engine.py` — validate manifest checkpoint whitelist, expose format resolution
- [x] 1.6 GREEN: Write tests in `test_workflow_engine.py` — whitelist rejection, format→dimension mapping

## Phase 2: Core Implementation — API + Modal Gate

- [x] 2.1 RED: Write test in `test_generation_models.py` for workflow/format validation
- [x] 2.2 GREEN: Modify `api/src/features/generation/models.py` — add `workflow`, `format` fields
- [x] 2.3 RED: Write test in `test_generation_service.py` for format→manifest-dim expansion
- [x] 2.4 GREEN: Modify `api/src/features/generation/router.py` — pass normalized workflow + format
- [x] 2.5 GREEN: Modify `api/src/features/generation/service.py` — normalize workflow name, expand format
- [x] 2.6 Add whitelist entry in `api/src/shared/modal_config.py` — premium checkpoint filename
- [x] 2.7 Write integration tests in `test_generation_router.py` — 202 accepted, invalid format 422, cache miss 500

## Phase 3: Frontend — Product Controls

 - [x] 3.1 RED: Write test in `generationStore.test.ts` for product_premium workflow type
 - [x] 3.2 GREEN: Modify `view/src/stores/generationStore.ts` — add product_premium workflow + format state
 - [x] 3.3 RED: Write test in `Sidebar.test.tsx` for product chip + no style menu
 - [x] 3.4 GREEN: Modify `view/src/components/studio/Sidebar.tsx` — add Product chip, format toggle, hide checkpoint/LoRA
 - [x] 3.5 Modify `view/src/lib/api.ts` — submit product workflow payload

## Phase 4: Verification

- [x] 4.1 Run `python3 -m pytest` — all backend tests pass
- [x] 4.2 Run frontend test suite — all component/store tests pass
- [x] 4.3 Manual smoke: POST /generate with product_premium → 202 + job_id
- [x] 4.4 Verify rollback: removing workflow dir + whitelist entry returns to clean state
