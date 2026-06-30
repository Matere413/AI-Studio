# Tasks: SDD 4 Orchestrator Agent

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450-650 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 backend orchestration → PR 2 frontend contract/UI |
| Delivery strategy | chained PRs |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Backend planner/orchestrator + safe dispatch | PR 1 | Base on main; include backend tests and API contract checks. |
| 2 | Frontend prompt-first client + stage timeline | PR 2 | Base on PR 1 branch; include UI state tests and DTO cleanup. |

## Phase 1: Backend Foundation

- [x] 1.1 Add `api/src/features/generation/models.py` request/response types for `OrchestrateRequest`, `PlannerDecision`, `OrchestrateResponse`, stage states, and planner error envelopes.
- [x] 1.2 Create `api/src/features/generation/planner.py` with a configurable `PlannerClient` interface and strict JSON prompt/schema validation for planner output.

## Phase 2: Backend Orchestration

- [x] 2.1 Create `api/src/features/generation/orchestrator.py` to validate workflow allowlists, confidence thresholds, asset-role mapping, and rejection of raw graph payloads.
- [x] 2.2 Add `orchestrate(...)` to `api/src/features/generation/service.py` so valid plans reuse existing typed dispatch paths and blocked plans return clarification/missing-asset outcomes.
- [x] 2.3 Update `api/src/features/generation/router.py` to expose `POST /generate/orchestrate` while preserving current session and existing asset-resolver wiring; `api/app.py` was not changed in PR 1.

## Phase 3: Frontend Wiring

- [x] 3.1 Update `view/src/features/chat/domain/dto.ts` and `view/src/features/chat/application/build-generate-request.ts` for prompt-first orchestration payloads and removal of stale `identidad_gguf` assumptions.
- [x] 3.2 Add `view/src/shared/infrastructure/api-client.ts` orchestration call and normalize outcomes into `job_started`, `clarification_required`, `missing_asset`, and `error`.
- [x] 3.3 Update chat sidebar components under `view/src/features/chat/presentation/components/*` to keep `Chat` and `Manual` tabs, show selected assets, and render planning/validation/dispatch/generation stages.

## Phase 4: Testing / Verification

- [x] 4.1 Add backend tests in `api/src/tests/test_orchestrator_agent.py` for schema rejection, ambiguity clarification, missing assets, unauthorized assets, and safe dispatch.
- [x] 4.2 Add frontend contract/UI tests under `view/src/features/chat/**/__tests__/*` for request building, outcome normalization, stage timeline rendering, and hidden default workflow controls.
- [x] 4.3 Verify `/generate/orchestrate` returns job, clarification, or missing-asset responses exactly as specified in `specs/orchestrator-agent/spec.md` and `specs/image-generation/spec.md`.

## Phase 5: Cleanup / Documentation

- [x] 5.1 Remove obsolete default manual workflow assumptions from chat-facing copy and any remaining references to `identidad_gguf` in the orchestration path.
