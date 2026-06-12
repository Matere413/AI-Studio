# Tasks: MVP Generation Endpoint

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 420-520 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 schemas/state → PR 2 service/worker → PR 3 router/app/tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Lock request/response/event contracts and job state abstraction | PR 1 | Base from tracker branch; write RED tests first. |
| 2 | Implement job submission and ComfyUI execution plumbing | PR 2 | Depends on PR 1; keep worker isolated. |
| 3 | Wire FastAPI/Modal app and end-to-end flow | PR 3 | Depends on PR 2; validate POST + WS lifecycle. |

## Phase 1: RED — Contracts

- [x] 1.1 Add failing pytest cases for `GenerateRequest`, `GenerateResponse`, and `JobEvent` in `src/tests/test_generation_models.py`.
- [x] 1.2 Add failing validation tests for `/generate` payload rejection and terminal WS error shape in `src/tests/test_generation_router.py`.
- [x] 1.3 Add failing tests for `src/shared/job_store.py` lifecycle transitions (`pending` → `running` → terminal) and reconnect lookup.

## Phase 2: GREEN — Core Types and State

- [x] 2.1 Implement `src/features/generation/models.py` with strict Pydantic schemas matching the spec payloads.
- [x] 2.2 Implement `src/shared/job_store.py` as the in-memory MVP contract for create/get/update/terminal state.
- [x] 2.3 Add `src/shared/modal_config.py` plus any package `__init__.py` files needed for shared imports.

## Phase 3: GREEN — Generation Flow

- [x] 3.1 Implement `src/features/generation/service.py` to create jobs, enqueue Modal work, and map failures to terminal errors.
- [x] 3.2 Implement `src/features/generation/modal_tasks.py` to mutate the ComfyUI payload and execute the GPU workflow.
- [x] 3.3 Implement `src/features/generation/router.py` for `POST /generate` and `WS /ws/generate/{job_id}` with polling/resume semantics.
- [ ] 3.4 Update `app.py` to mount the FastAPI ASGI app and refactor `api.py` into `src/shared/comfy_client.py`.

## Phase 4: REFACTOR — Integration Proof

- [ ] 4.1 Add end-to-end pytest coverage for accepted request, validation failure, unknown job error, reconnect, and completed stream.
- [ ] 4.2 Remove stub logic/comments from `app.py` and obsolete synchronous client assumptions from `api.py`.
