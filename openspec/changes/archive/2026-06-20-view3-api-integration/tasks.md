# Tasks: View3 API Integration

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 800–900 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain (PR 3 of 3 ✅) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain (PR 3 of 3 ✅)
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Infrastructure + Domain DTOs + unit tests | PR 1 | Foundation; no UI changes; ~280 lines |
| 2 | Application hooks + image proxy + integration tests | PR 2 | Depends on PR 1; ~300 lines |
| 3 | UI wiring + page.tsx integration | PR 3 | Depends on PR 2; removes mocks; ~280 lines |

## Phase 1: Foundation — Infrastructure & Domain

- [x] 1.1 Create `view3/src/shared/infrastructure/env.ts` — read `NEXT_PUBLIC_API_BASE_URL`, derive WS URL (`https→wss`)
- [x] 1.2 Create `view3/src/shared/infrastructure/api-client.ts` — `submitGenerate(dto)`, `getWsUrl(jobId)`, `normalizeError(status, body)`, `fetchImageBinary(jobId)`
- [x] 1.3 Create `view3/src/shared/infrastructure/index.ts` — barrel re-export
- [x] 1.4 Create `view3/src/features/chat/domain/dto.ts` — `WorkflowName` union, discriminated `GenerateRequest` types, `validateRequest()`
- [x] 1.5 Create `view3/src/features/studio/domain/dto.ts` — `GenerateResponse`, `JobEvent`, `JobEventResult`, `JobEventError`
- [x] 1.6 Update barrel files: `features/chat/domain/index.ts`, `features/studio/domain/index.ts` — re-export new DTOs
- [x] 1.7 Write unit tests for `normalizeError` — 422→validation_error, 500→operational, unknown→fallback
- [x] 1.8 Write unit tests for `validateRequest` (DTO contract validation) — verify field inclusion/exclusion per workflow (spec scenarios: flux2_txt2img, flux2_editing, identidad_gguf)

## Phase 2: Application Layer & Image Proxy ✅

- [x] 2.1 Create `view3/src/features/chat/application/build-generate-request.ts` — pure function `(prompt, workflow, params) → GenerateRequest`
- [x] 2.2 Create `view3/src/features/chat/application/use-generation-job.ts` — `useReducer`-based WS hook: connect to `/ws/generate/{job_id}`, dispatch events, retry 3× (1s/2s/4s), expose `retry()`, states: connecting|streaming|completed|error|exhausted
- [x] 2.3 Update `features/chat/application/index.ts` — re-export hook and builder
- [x] 2.4 Update `features/chat/infrastructure/index.ts` — re-export shared infrastructure
- [x] 2.5 Create `view3/src/app/api/images/[jobId]/route.ts` — proxy GET to `{API_BASE_URL}/images/{jobId}`, stream binary with upstream Content-Type, 404→`{code, detail}`
- [x] 2.6 Write integration test for `useGenerationJob` — mock WebSocket, assert state transitions (connect→progress→complete), retry exhaustion, retry() reset
- [x] 2.7 Write integration test for image proxy — mock fetch, assert 200 streams binary, 404 returns error JSON

## Phase 3: UI Wiring & Integration ✅

- [x] 3.1 Modify `ChatComposer.tsx` — replace Aspect Ratio `PillSelect` with Workflow Selector (`flux2_txt2img|flux2_editing|identidad_gguf`), toggle identity panel, wire `onSend` to `submitGenerate(buildGenerateRequest(...))`
- [x] 3.2 Modify `MessageList.tsx` — accept real `ChatMessage[]` prop, render job event cards (progress/message/error), remove `MockMessage`
- [x] 3.3 Modify `ChatSidebar.tsx` — accept live state props instead of `MOCK_MESSAGES`
- [x] 3.4 Modify `StudioCanvas.tsx` — render result image via `/api/images/{jobId}`, show event status text
- [x] 3.5 Modify `StatusBar.tsx` — accept `status` + `progress` props, display `booting_server`/`downloading_weights`/`generating` with progress %
- [x] 3.6 Modify `page.tsx` — add `useReducer` for `StudioState` (selectedWorkflow, currentJob, generationState, messages, error), remove `MOCK_MESSAGES` imports, wire `useGenerationJob` and `submitGenerate` to children
- [x] 3.7 Verify end-to-end: submit prompt → WS stream updates chat/status/canvas → image renders via proxy

## Phase 4: Verification Fixes ✅

- [x] 4.1 Fix `flux2_editing` UI submission path — add image file input to ChatComposer, wire `imageBase64` through page.tsx `handleSend`, convert FileReader data URL to raw base64 (Critical 1)
- [x] 4.2 Create `view3/src/lib/api.ts` — re-export barrel satisfying spec-required contract (`submitGenerate`, `getWsUrl`) (Critical 2)
- [x] 4.3 Add WS reconnect-success test — prove `wsReducer` handles disconnect → reconnect → stream resumed lifecycle, export and verify `RETRY_DELAYS_MS` backoff constants (Critical 3)
- [x] 4.4 Add `generationState` and `sessionHistory` to `StudioState` — sync `generationState` from genJob via `SET_GENERATION_STATE` effect; rename `messages` → `sessionHistory` to match spec contract (Critical 4)
- [x] 4.5 Verify all tests pass (143 tests) and type-check (0 errors)
