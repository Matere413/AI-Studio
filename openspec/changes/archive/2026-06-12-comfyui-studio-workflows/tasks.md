# Tasks: ComfyUI Studio Workflows

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 700-900 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Manifest + schema foundation | PR 1 | Base = main; includes validation tests for `src/shared/workflows/models.py` and `src/workflows/txt2img/manifest.yaml`. |
| 2 | Model cache service | PR 2 | Base = PR 1; adds `src/shared/workflows/cache.py` and cache-hit/miss tests. |
| 3 | Workflow execution + API wiring | PR 3 | Base = PR 2; adds `src/shared/workflows/engine.py`, endpoint updates, and integration tests. |

## Phase 1: Foundation / Workflow Contracts

- [x] 1.1 Create `src/shared/workflows/models.py` with `NodeMapping`, `ManifestSchema`, and request schemas for declared workflow inputs.
- [x] 1.2 Add `src/workflows/txt2img/workflow.json` and `src/workflows/txt2img/manifest.yaml` with semantic-to-node mappings.
- [x] 1.3 Add package init files for `src/shared/workflows/`, `src/features/editing/`, and `src/features/controlnet/`.

## Phase 2: Core Engine and Cache

- [x] 2.1 Implement `src/shared/workflows/engine.py` to load template + manifest, validate references, and resolve params into a graph.
- [x] 2.2 Implement `src/shared/workflows/cache.py` with Modal `download_model()` for cache-hit/miss behavior and failure surfacing.
- [x] 2.3 Update `src/features/generation/models.py` to accept `checkpoint_url`, `lora_url`, and workflow-specific inputs with `extra="forbid"`.
- [x] 2.4 Refactor `src/features/generation/service.py` to resolve workflow selection before enqueueing Modal work.

## Phase 3: Integration / Feature Endpoints

- [x] 3.1 Update `src/features/generation/router.py` to call the new engine/cache path while preserving `202` + `job_id`.
- [x] 3.2 Create `src/features/editing/router.py` and `src/features/controlnet/router.py` with img2img/control-image request validation.
- [x] 3.3 Wire the new routers into `app.py` and keep backward-compatible generation imports.

## Phase 4: Testing / Cleanup

- [x] 4.1 Add tests for manifest validation in `src/tests/test_workflow_models.py` and engine parameter mapping in `src/tests/test_workflow_engine.py`.
- [x] 4.2 Add cache tests in `src/tests/test_model_cache.py` for download, reuse, and invalid URL failure paths.
- [x] 4.3 Update `src/tests/test_generation_router.py` and `src/tests/test_e2e_generation.py` for `/generate` workflow parameters and mocked execution.
- [x] 4.4 Remove prompt-specific payload assumptions from `src/features/generation/modal_tasks.py` if the new engine fully replaces them.
