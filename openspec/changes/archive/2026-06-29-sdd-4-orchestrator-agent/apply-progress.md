# Apply Progress: SDD 4 Orchestrator Agent

## Slice

- Mode: Strict TDD
- Delivery: stacked PR slice
- Current work unit: PR 2 frontend contract/UI, merged with completed PR 1 backend orchestration / planner contract evidence
- Boundary: cumulative SDD 4 implementation. PR 1 completed backend models, planner contract, orchestrator validation/dispatch, router endpoint, and backend tests. PR 2 completed frontend prompt-first orchestration request/client contract, Chat/Manual sidebar tabs, stage timeline UI, selected-asset context, and frontend tests.

## Completed Tasks

- [x] 1.1 Add `api/src/features/generation/models.py` request/response types for orchestration.
- [x] 1.2 Create `api/src/features/generation/planner.py` with `PlannerClient` and strict JSON parsing.
- [x] 2.1 Create `api/src/features/generation/orchestrator.py` for allowlist, confidence, asset-role, and raw graph validation.
- [x] 2.2 Add `GenerationService.orchestrate(...)` to reuse typed dispatch and return blocked outcomes.
- [x] 2.3 Expose `POST /generate/orchestrate` in the generation router while preserving session and asset resolver wiring.
- [x] 3.1 Update frontend DTO/request builder for prompt-first orchestration payloads and stale default workflow omission.
- [x] 3.2 Add frontend API client orchestration call and normalize `job_started`, `clarification_required`, `missing_asset`, and `error` outcomes.
- [x] 3.3 Update chat sidebar to keep `Chat` and `Manual` tabs, selected assets, and planning/validation/dispatch/generation stages.
- [x] 4.1 Add backend tests for schema rejection, ambiguity clarification, missing assets, unauthorized assets, and safe dispatch.
- [x] 4.2 Add frontend contract/UI tests for request building, outcome normalization, stage timeline rendering, and hidden default workflow controls.
- [x] 4.3 Verify orchestration endpoint job and clarification outcomes in focused tests.
- [x] 5.1 Remove obsolete default manual workflow assumptions from the prompt-first chat path and keep `identidad_gguf` out of orchestration requests.

## Remediation Completed — PR 1 Backend Fresh Review

- [x] Normalize planner provider/network/timeout/malformed-response failures into safe orchestration `error` responses.
- [x] Defer `flux2_editing` orchestration for PR 1 by removing it from the backend planner allowlist; legacy typed `/generate` editing remains unchanged.
- [x] Return non-2xx HTTP status for orchestration `error` outcomes while preserving `200` guidance responses for clarification and missing assets.
- [x] Mark jobs as terminal `error` when dispatch fails after job creation.
- [x] Preflight real asset resolver ownership/not-found failures and map them to safe `missing_asset` guidance before dispatch.

## Remediation Completed — PR 1 Backend Second Re-review

- [x] Added planner provider invalid-response-shape contract coverage for `EnvPlannerClient.plan()` and safe orchestration mapping for malformed provider responses.
- [x] Added structured production observability for orchestration failures: planner provider failures, malformed planner/provider responses, unsupported workflows, validation/dispatch failures, and terminal-state recovery failures.
- [x] Changed `_mark_job_failed()` to report terminal-state recovery success/failure and log failed recovery instead of silently swallowing update exceptions.
- [x] Removed dead imports from `api/src/features/generation/router.py`.
- [x] Corrected `tasks.md` wording: PR 1 exposes `/generate/orchestrate` in the router and does not change `api/app.py`.
- [x] Documented in code that PR 1 planner dispatch support intentionally excludes asset-backed `flux2_editing` despite the broader known workflow enum.

## Remediation Completed — PR 1 Backend Final Re-review

- [x] Sanitized client-facing `planner_schema_invalid` orchestration errors so raw Pydantic/provider validation content cannot leak through `error_detail` or router JSON responses.
- [x] Refactored orchestration error construction around a small `FailureContext` dataclass to separate response state from observability metadata.
- [x] Deduplicated post-job dispatch failure recovery into a single helper while preserving terminal job failure handling and observability behavior.

## Remediation Completed — PR 2 Frontend Fresh Review

- [x] Added rendered `ChatComposer` component tests for Chat/Manual tabs, tab switching, selected-assets display, manual controls visibility, and prompt retention on failed orchestration submission.
- [x] Added orchestration pending semantics: chat submit now awaits acceptance before clearing input, returns `false` for duplicate/failed submissions, and disables the composer while orchestration planning/submission is pending.
- [x] Added safe successful-response normalization for `/generate/orchestrate`; malformed 2xx `job_started` responses without `job_id` become `invalid_orchestration_response` errors instead of starting an empty job.
- [x] Sanitized client-visible orchestration error copy and planner invalid-response details while keeping stable error codes for debugging.
- [x] Replaced implicit “all done assets are selected” behavior with explicit selected asset state, asset selection toggles, selected-only chat context display, and selected-only orchestration payloads.
- [x] Kept Manual tab controls separate from the prompt-first Chat path; manual legacy fields remain only in manual request builder/UI paths and are not sent by orchestration requests.
- [x] Fixed the surgical build blocker by removing the stale `@typescript-eslint/no-unused-vars` eslint-disable reference from `AssetsDrawer.tsx`; `pnpm build` now completes with only existing warnings.

## Remediation Completed — PR 2 Frontend Final Readability Cleanup

- [x] Centralized orchestration stage order/default helpers in `view/src/features/chat/domain/dto.ts` so `page.tsx`, `orchestration-ui.ts`, and `api-client.ts` no longer duplicate planning/validation/dispatch/generation fallback literals.
- [x] Grouped `ChatSidebar`/`ChatComposer` props by concern: submit state, manual controls, selected assets, and orchestration state, preserving behavior while clarifying Chat vs Manual boundaries.
- [x] Recorded the remaining `ai-studio-session-id` JS-readable cookie/localStorage issue as future SDD 8 security debt in `developmentPlan.md`; no HttpOnly/server-owned session implementation was done in this cleanup.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_orchestrator_agent.py` | Unit | N/A (new orchestration models) | ✅ Import failure for missing `OrchestrateRequest`/`PlannerDecision` | ✅ `12 passed` focused | ✅ Valid request + raw graph rejection | ✅ Strict Pydantic models with shared literals |
| 1.2 | `api/src/tests/test_orchestrator_agent.py` | Unit | N/A (new planner module) | ✅ Import failure for missing `parse_planner_decision` | ✅ `12 passed` focused | ✅ Valid JSON + malformed output rejection | ✅ `PlannerClient` protocol and env-backed client separated |
| 2.1 | `api/src/tests/test_orchestrator_agent.py` | Unit | N/A (new orchestrator module) | ✅ Import failure for missing `Orchestrator` | ✅ `12 passed` focused | ✅ Clarification, missing asset, unauthorized asset, unsafe workflow, extraction dispatch | ✅ Centralized allowlists and stage helpers |
| 2.2 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Existing generation service tests covered by focused suite | ✅ Service orchestration behavior demanded by orchestrator tests | ✅ `140 passed` focused generation suite | ✅ Valid dispatch + blocked outcomes | ✅ Service delegates orchestration boundary without changing existing dispatch |
| 2.3 | `api/src/tests/test_orchestrator_agent.py` | Integration | ✅ Existing generation router tests covered by focused suite | ✅ Endpoint tests referenced missing route/client injection | ✅ `140 passed` focused generation suite | ✅ `202 job_started` + `200 clarification_required` | ✅ Injectable planner setter mirrors asset resolver wiring |
| 4.1 | `api/src/tests/test_orchestrator_agent.py` | Unit/Integration | N/A (new test file) | ✅ Initial focused run failed on missing production symbols | ✅ `12 passed` focused | ✅ 12 cases across model, planner, orchestrator, and endpoint behavior | ✅ Removed invalid unsafe-workflow fixture by using a planner double |
| 4.3 | `api/src/tests/test_orchestrator_agent.py` | Integration | ✅ Existing router contract tests still passed | ✅ Endpoint contract tests added before route implementation | ✅ `614 passed` full backend suite | ✅ Job and clarification HTTP status/outcome coverage | ✅ Router returns 202 only for `job_started`; blocked outcomes remain 200 |
| Remediation 1 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Planner parser tests existed | ✅ `EnvPlannerClient` leaked `URLError`; orchestrator leaked `TimeoutError` | ✅ `18 passed` focused | ✅ Provider unavailable + invalid response normalized through safe error codes | ✅ Planner error mapping centralized in orchestrator |
| Remediation 2 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Existing Flux 2 txt2img dispatch test | ✅ `flux2_editing` reached dispatch and failed with missing base64 | ✅ `18 passed` focused | ✅ Unsupported workflow rejected before dispatch | ✅ Planner prompt/allowlist no longer advertises editing in PR 1 |
| Remediation 3 | `api/src/tests/test_orchestrator_agent.py` | Integration | ✅ Existing 202/200 endpoint tests | ✅ Error outcome returned HTTP 200 | ✅ `18 passed` focused | ✅ `unsupported_workflow` returns 422 while guidance outcomes stay 200 | ✅ Router status mapping kept local to HTTP boundary |
| Remediation 4 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Job lifecycle store tests existed elsewhere | ✅ Dispatch failure returned error but left pending job | ✅ `18 passed` focused | ✅ Error response includes job_id and persisted job status `error` | ✅ Dispatch failures use generic safe detail |
| Remediation 5 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Unauthorized selected-id test existed | ✅ Resolver ownership/not-found exception was not checked before dispatch | ✅ `18 passed` focused | ✅ Resolver rejection returns `missing_asset` and skips dispatch | ✅ Resolver preflight added before job creation |
| Second remediation 1 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ `18 passed` focused before edits | ✅ Observability tests failed because `orchestrator._log` did not exist | ✅ `22 passed` focused | ✅ Invalid provider response shape + malformed provider response safe mapping | ✅ Provider invalid response detail remains sanitized |
| Second remediation 2 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ `18 passed` focused before edits | ✅ Unsupported workflow and dispatch recovery observability assertions failed | ✅ `22 passed` focused | ✅ Unsupported workflow, planner invalid response, terminal update failure | ✅ Centralized safe `orchestration_failure` metadata helper |
| Second remediation 3 | `api/src/tests/test_orchestrator_agent.py` | Unit | ✅ Existing dispatch failure terminal-state test | ✅ Store update failure was swallowed with no signal | ✅ `22 passed` focused | ✅ `_mark_job_failed()` logs `terminal_state_recovery_failed` and returns failure to caller | ✅ Clients still receive generic dispatch error only |
| Second remediation 4 | `api/src/features/generation/router.py` | Refactor | ✅ `22 passed` focused after behavior changes | ✅ Dead imports identified by review | ✅ `111 passed` focused generation regression | ➖ Structural cleanup only | ✅ Removed unused `Any` and `datetime/timezone` imports |
| Second remediation 5 | `openspec/changes/sdd-4-orchestrator-agent/tasks.md` | Documentation | ✅ Existing apply-progress note said `api/app.py` unchanged | ✅ Task wording contradicted apply-progress | ✅ Documentation updated | ➖ Single wording correction | ✅ Tasks and apply-progress now agree |
| Second remediation 6 | `api/src/features/generation/orchestrator.py` | Documentation | ✅ Existing `flux2_editing` deferred test | ✅ Broader enum could be confused with planner dispatch support | ✅ `22 passed` focused | ➖ Code comment clarification only | ✅ Code now distinguishes known workflows from PR 1 planner allowlist |
| Final remediation 1 | `api/src/tests/test_orchestrator_agent.py` | Unit/Integration | ✅ `22 passed` focused before edits | ✅ Schema-invalid planner response leaked raw provider/Pydantic content in `error_detail` | ✅ `24 passed` focused | ✅ Orchestrator unit + router non-2xx response both prove sanitized detail | ✅ Planner schema-invalid mapping uses deterministic safe message |
| Final remediation 2 | `api/src/features/generation/orchestrator.py` | Refactor | ✅ `24 passed` after security fix | ✅ `_error(...)` mixed response and observability metadata in a long parameter list | ✅ `24 passed` focused | ➖ Approval-style behavior preservation | ✅ Added `FailureContext` dataclass and updated callers |
| Final remediation 3 | `api/src/features/generation/orchestrator.py` | Refactor | ✅ `24 passed` after security fix | ✅ Dispatch failure recovery branches duplicated terminal state/error response logic | ✅ `24 passed` focused | ➖ Approval-style behavior preservation | ✅ Extracted `_dispatch_failure_response(...)` helper |
| 3.1 | `view/src/features/chat/application/__tests__/build-generate-request.test.ts` | Unit | ✅ 85 existing focused frontend tests passed before edits | ✅ Missing `buildOrchestrateRequest` export failed | ✅ 63 focused frontend tests passed | ✅ Selected assets, stale manual fields omitted, optional workspace context | ✅ Pure request builder added without changing legacy manual builder |
| 3.2 | `view/src/shared/infrastructure/__tests__/api-client.test.ts` | Unit | ✅ 85 existing focused frontend tests passed before edits | ✅ Missing `submitOrchestrate` export failed | ✅ 63 focused frontend tests passed | ✅ Job, clarification, missing-asset, and non-2xx error outcomes | ✅ Error normalization centralized for orchestration responses |
| 3.3 | `view/src/features/chat/presentation/__tests__/orchestration-ui.test.ts` | Unit | ✅ 85 existing focused frontend tests passed before edits | ✅ Missing orchestration UI helper module failed | ✅ 63 focused frontend tests passed | ✅ Chat/Manual tabs, hidden manual controls, backend stages, default stage chain | ✅ Pure UI-state helpers extracted and used by `ChatComposer` |
| 4.2 | `view/src/features/chat/application/__tests__/build-generate-request.test.ts`, `view/src/shared/infrastructure/__tests__/api-client.test.ts`, `view/src/features/chat/presentation/__tests__/orchestration-ui.test.ts` | Unit | ✅ 85 existing focused frontend tests passed before edits | ✅ New contract/UI tests failed on missing production exports | ✅ 261 frontend unit tests passed | ✅ Request, outcome, timeline, and hidden-manual-control cases | ✅ Component logic exercised through pure helpers to avoid brittle DOM/class assertions |
| 5.1 | `view/src/app/page.tsx`, `view/src/features/chat/presentation/components/ChatComposer.tsx` | Refactor/Contract | ✅ Focused frontend tests and typecheck passed before final refactor | ✅ Prompt-first path still built manual workflow requests before PR 2 | ✅ 63 focused frontend tests and `pnpm type-check` passed | ✅ Identity prompts use selected asset ids only, no `workflow_name`/`identidad_gguf` fields | ✅ Manual controls remain behind Manual tab while Chat submits orchestration requests |
| PR 2 remediation 1 | `view/src/features/chat/presentation/__tests__/chat-composer-render.test.ts` | Component | ✅ Existing pure helper tests only | ✅ Rendered component tests failed on prompt retention and initially proved test harness coverage gaps | ✅ Focused frontend remediation tests passed, 58 tests | ✅ Chat/Manual tabs, tab switching, selected assets, manual controls visibility, failed-submit prompt retention | ✅ Component test harness transpiles `ChatComposer.tsx` and stubs shared icons only |
| PR 2 remediation 2 | `view/src/shared/infrastructure/__tests__/api-client.test.ts` | Unit | ✅ Existing outcome normalization tests | ✅ Malformed 2xx `job_started` without `job_id` was accepted; raw invalid-response detail passed through | ✅ Focused frontend remediation tests passed, 58 tests | ✅ Invalid 2xx response + sanitized planner invalid-response detail | ✅ Successful response normalization added beside non-2xx normalization |
| PR 2 remediation 3 | `view/src/features/assets/__tests__/reducer.test.ts` | Unit | ✅ Asset reducer tests existed | ✅ Explicit selected asset state/actions did not exist | ✅ Focused frontend remediation tests passed, 58 tests | ✅ Toggle selected asset + remove deleted selected asset | ✅ Selection state lives beside session assets and updates on server-id replacement |
| PR 2 remediation 4 | `view/src/features/chat/presentation/__tests__/orchestration-ui.test.ts` | Unit | ✅ Stage/tabs helper tests existed | ✅ Safe client-facing error copy helper missing | ✅ Focused frontend remediation tests passed, 58 tests | ✅ Raw provider/backend detail not surfaced to users | ✅ User-facing orchestration messaging centralized |
| PR 2 final readability 1 | `view/src/features/chat/presentation/__tests__/orchestration-ui.test.ts`, `view/src/shared/infrastructure/__tests__/api-client.test.ts` | Refactor | ✅ Existing stage timeline and response-normalization tests covered behavior | ➖ Behavior-preserving cleanup; no new failing behavior expected | ✅ Focused frontend tests passed, 42 tests | ✅ Default/pending and blocked stage fallbacks still render/normalize correctly | ✅ Shared orchestration stage helpers now define stage semantics once |
| PR 2 final readability 2 | `view/src/features/chat/presentation/__tests__/chat-composer-render.test.ts` | Refactor | ✅ Rendered component tests covered Chat/Manual boundary and failed-submit retention | ➖ Behavior-preserving prop grouping; no new failing behavior expected | ✅ Focused frontend tests passed, 42 tests | ✅ Chat/Manual tabs, selected assets, and prompt retention remain unchanged | ✅ Props grouped by submit, manual controls, selected assets, and orchestration state |
| PR 2 final security-debt plan | `developmentPlan.md` | Documentation | ✅ Existing SDD 7 was complete, so new debt needed a pending roadmap item | ➖ Documentation-only future work item | ✅ `pnpm type-check`, `pnpm test:unit`, and `pnpm build` passed | ➖ No runtime behavior change | ✅ SDD 8 now captures the server-owned HttpOnly session boundary goal |

## Verification

- `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 12 tests.
- `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_orchestrator_agent.py` — passed, 140 tests, 5 existing async Modal warnings.
- `python3 -m pytest src/tests` — passed, 614 tests, 11 existing async Modal warnings.
- Remediation RED: `python3 -m pytest src/tests/test_orchestrator_agent.py` — failed, 6 failures covering planner provider normalization, deferred `flux2_editing`, resolver rejection, dispatch failure terminal state, and non-2xx error HTTP status.
- Remediation GREEN: `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 18 tests.
- Remediation focused regression: `python3 -m pytest src/tests/test_orchestrator_agent.py src/tests/test_generation_service.py src/tests/test_generation_router.py` — passed, 107 tests, 5 existing async Modal warnings.
- Remediation full backend regression: `python3 -m pytest src/tests` — passed, 620 tests, 11 existing async Modal warnings.
- Second remediation baseline: `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 18 tests.
- Second remediation RED: `python3 -m pytest src/tests/test_orchestrator_agent.py` — failed, 3 failures because orchestration observability/logging did not exist yet.
- Second remediation GREEN: `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 22 tests.
- Second remediation focused regression: `python3 -m pytest src/tests/test_orchestrator_agent.py src/tests/test_generation_service.py src/tests/test_generation_router.py` — passed, 111 tests, 5 existing async Modal warnings.
- Second remediation full backend regression: `python3 -m pytest src/tests` — passed, 624 tests, 11 existing async Modal warnings.
- Final remediation baseline: `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 22 tests.
- Final remediation RED: `python3 -m pytest src/tests/test_orchestrator_agent.py` — failed, 2 failures proving raw schema-invalid planner content leaked through orchestrator and router `error_detail`.
- Final remediation GREEN: `python3 -m pytest src/tests/test_orchestrator_agent.py` — passed, 24 tests.
- Final remediation focused regression: `python3 -m pytest src/tests/test_orchestrator_agent.py src/tests/test_generation_service.py src/tests/test_generation_router.py` — passed, 113 tests, 5 existing async Modal warnings.
- Final remediation full backend regression: `python3 -m pytest src/tests` — passed, 626 tests, 11 existing async Modal warnings.
- PR 2 frontend safety net: `NODE_OPTIONS="--experimental-strip-types" node --test "src/features/chat/application/__tests__/build-generate-request.test.ts" "src/shared/infrastructure/__tests__/api-client.test.ts" "src/features/chat/domain/__tests__/dto.test.ts"` — passed, 85 tests.
- PR 2 frontend RED: `NODE_OPTIONS="--experimental-strip-types" node --test "src/features/chat/application/__tests__/build-generate-request.test.ts" "src/shared/infrastructure/__tests__/api-client.test.ts" "src/features/chat/presentation/__tests__/chat-sidebar.test.tsx"` — failed on missing `buildOrchestrateRequest`, missing `submitOrchestrate`, and unsupported `.tsx` test execution; UI tests were adjusted to pure TS helper tests before GREEN.
- PR 2 frontend GREEN: `NODE_OPTIONS="--experimental-strip-types" node --test "src/features/chat/application/__tests__/build-generate-request.test.ts" "src/shared/infrastructure/__tests__/api-client.test.ts" "src/features/chat/presentation/__tests__/orchestration-ui.test.ts"` — passed, 63 tests.
- PR 2 frontend typecheck: `pnpm type-check` — passed.
- PR 2 frontend full unit regression: `pnpm test:unit` — passed, 261 tests; existing module-type/localStorage warnings and expected proxy error logs remain.
- PR 2 frontend build attempt: `pnpm build` — failed after successful compile/type validity on pre-existing lint configuration error `Definition for rule '@typescript-eslint/no-unused-vars' was not found` in `src/features/assets/presentation/components/AssetsDrawer.tsx`, plus pre-existing warnings in assets code.
- PR 2 remediation RED: `NODE_OPTIONS="--experimental-strip-types" node --test "src/shared/infrastructure/__tests__/api-client.test.ts" "src/features/chat/presentation/__tests__/orchestration-ui.test.ts" "src/features/assets/__tests__/reducer.test.ts" "src/features/chat/presentation/__tests__/chat-composer-render.test.ts"` — failed, 7 failures covering missing safe UI copy helper, missing explicit asset selection state, prompt clearing after failed submit, malformed 2xx `job_started` acceptance, and raw planner invalid-response detail passthrough.
- PR 2 remediation GREEN focused: same focused command — passed, 58 tests.
- PR 2 remediation typecheck: `pnpm type-check` — passed.
- PR 2 remediation full frontend unit regression: `pnpm test:unit` — passed, 268 tests; existing module-type/localStorage warnings and expected proxy error logs remain.
- PR 2 remediation build: `pnpm build` — passed. Existing warnings remain in `use-upload.ts` (`react-hooks/exhaustive-deps`) and `AssetList.tsx` (`@next/next/no-img-element`).
- PR 2 final readability focused regression: `NODE_OPTIONS="--experimental-strip-types" node --test "src/features/chat/presentation/__tests__/orchestration-ui.test.ts" "src/shared/infrastructure/__tests__/api-client.test.ts" "src/features/chat/presentation/__tests__/chat-composer-render.test.ts"` — passed, 42 tests; existing module-type/localStorage warnings remain.
- PR 2 final readability typecheck: `pnpm type-check` — passed.
- PR 2 final readability full frontend unit regression: `pnpm test:unit` — passed, 268 tests; existing module-type/localStorage warnings and expected proxy error logs remain.
- PR 2 final readability build: `pnpm build` — passed. Existing warnings remain in `use-upload.ts` (`react-hooks/exhaustive-deps`) and `AssetList.tsx` (`@next/next/no-img-element`).

## Notes

- Planner provider strategy follows the MVP decision: an injectable `PlannerClient` protocol plus `EnvPlannerClient` configured by `PLANNER_API_URL`, `PLANNER_API_KEY`, and `PLANNER_MODEL` for an external OpenAI-compatible provider.
- PR 1 intentionally defers prompt-first `flux2_editing` orchestration because the current Modal path requires `image_base64`; asset-backed editing can be restored in a later slice when it has an explicit resolver-to-base64 dispatch path.
- `api/app.py` remains unchanged in PR 1: existing router-level asset resolver wiring is sufficient for `/generate/orchestrate`; `tasks.md` now records the chosen `stacked-to-main` chain strategy.
- Orchestration failures now emit structured safe metadata via `orchestration_failure`; failed terminal-state recovery emits `terminal_state_recovery_failed` and is reported internally without leaking provider/DB/dispatch details to clients.
- Schema-invalid planner responses now return deterministic client-facing detail: `Planner response does not match the required schema`; raw provider/Pydantic validation content is not serialized in orchestration responses.
- PR 1 did not modify frontend files; PR 2 completed the frontend contract/UI slice.
- PR 2 switches the default chat submit path to `POST /generate/orchestrate`; manual controls remain available only in the `Manual` tab.
- Prompt-first orchestration requests carry `prompt`, `selected_asset_ids`, and optional `workspace_context`; they do not send `workflow_name`, `image_url`, geometry fields, or `identidad_gguf` defaults.
- PR 2 remediation makes selected assets explicit: only assets toggled as selected in the drawer are displayed in the Chat context and sent as `selected_asset_ids`; uploaded-but-unselected assets are not sent.
- PR 2 remediation treats orchestration provider/network/invalid-response failures as unaccepted submissions from the composer perspective, preserving the prompt for retry while still adding safe user-facing error feedback to chat history.
- Final readability cleanup keeps orchestration stage semantics in the chat domain DTO helpers and uses those helpers for UI pending state, API blocked fallbacks, and initial running state.
- The remaining session-token security warning is intentionally deferred to pending SDD 8: migrate to a server-owned HttpOnly/session boundary and stop treating JS-readable `ai-studio-session-id` as an auth/ownership secret.

## Remaining Tasks

- None. All SDD 4 implementation tasks are complete; verification/archive remain separate phases.
