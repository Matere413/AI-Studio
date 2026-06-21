## Verification Report

**Change**: view3-api-integration  
**Version**: N/A  
**Mode**: Standard  
**Generated**: 2026-06-20

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 27 |
| Tasks complete | 27 |
| Tasks incomplete | 0 |
| Spec scenarios found | 15 |
| Spec scenarios compliant | 7 |
| Spec scenarios partial | 6 |
| Spec scenarios untested | 1 |
| Spec scenarios failing/deviating | 1 |

### Build & Tests Execution

**Type-check**: ✅ Passed

```text
$ cd view3 && pnpm type-check
$ tsc --noEmit
```

**Unit tests**: ✅ 143 passed / 0 failed / 0 skipped

```text
$ cd view3 && bash test/unit-tests.sh
ℹ tests 143
ℹ suites 19
ℹ pass 143
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 30415.312709
```

**Coverage**: ➖ Not available — no coverage command or threshold is configured for this change.

### Spec Compliance Matrix

| Requirement | Scenario | Runtime Test Evidence | Result |
|-------------|----------|-----------------------|--------|
| Strict HTTP Client for POST `/api/generate` | Flux 2 txt2img | `build-generate-request.test.ts` + `dto.test.ts` verify `workflow_name`, `prompt`, optional `use_turbo`, and no legacy fields. | ✅ COMPLIANT |
| Strict HTTP Client for POST `/api/generate` | Flux 2 editing | Builder/DTO tests pass and `ChatComposer.tsx` now converts file data URLs to raw base64, but `page.tsx` reads `editingReferenceBase64` inside `handleSend` without listing it in the `useCallback` dependency array, so the send handler can keep the pre-selection `null` value and fail the real UI submission. | ❌ FAILING |
| Strict HTTP Client for POST `/api/generate` | Identity GGUF | Builder/DTO tests verify `image_url`; UI source wires `referenceFaceUrl` through `page.tsx`. No component-level submit test covers the full UI path. | ⚠️ PARTIAL |
| Typed Error Envelope Handling | Validation error | `normalize-error.test.ts` and `api-client.test.ts` verify 422 `detail` maps to `{ code: "validation_error", detail }`. | ✅ COMPLIANT |
| Typed Error Envelope Handling | Operational error | `normalize-error.test.ts` and `api-client.test.ts` verify 500 `{ error: { code, detail } }` passthrough. | ✅ COMPLIANT |
| WebSocket Resilience with Retry Button | Reconnect succeeds | `use-generation-job.test.ts` now covers reducer sequence `WS_ERROR → CONNECTING → CONNECTED → stream resumes`; no hook/WebSocket/timer test proves `onclose` schedules reconnect and resumes from the actual `useGenerationJob` effect. | ⚠️ PARTIAL |
| WebSocket Resilience with Retry Button | Retries exhausted | `use-generation-job.test.ts` verifies reducer exhaustion after 3 disconnects; no hook-level test proves the backoff timers exhaust through actual WebSocket close events. | ⚠️ PARTIAL |
| WebSocket Resilience with Retry Button | Retry clicked | `StudioCanvas.tsx` renders a retry button in `exhausted` state and reducer tests verify `RETRY_RESET`; no runtime click/hook test proves the button invokes reconnect. | ⚠️ PARTIAL |
| Next.js Image Proxy | Proxy serves image | `image-proxy-route.test.ts` verifies 200 binary stream and upstream `Content-Type`. | ✅ COMPLIANT |
| Next.js Image Proxy | Proxy upstream 404 | `image-proxy-route.test.ts` verifies 404 JSON `{ code, detail }`. | ✅ COMPLIANT |
| Manual Workflow Selector | Workflow selection | `studio-reducer.test.ts` verifies workflow update; source shows selector and editing controls. No component test covers rendered selector behavior. | ⚠️ PARTIAL |
| Manual Workflow Selector | Identity workflow activates panel | Static evidence in `ChatComposer.tsx` shows panel when `workflow === "identidad_gguf"`; no runtime/component test covers the render behavior. | ❌ UNTESTED |
| Manual Workflow Selector | Switching away resets params | `studio-reducer.test.ts` verifies clearing identity URL and editing base64 when switching away; no component test verifies panel disable. | ⚠️ PARTIAL |
| API Integration Layer | Submit with strict DTO | `api-client.test.ts` verifies POST to `/api/generate`, JSON body, and `{ job_id, status }` response. `src/lib/api.ts` re-exports `submitGenerate` and `getWsUrl`. | ✅ COMPLIANT |
| useReducer Store Contract | Default workflow | `studio-reducer.test.ts` verifies initial `selectedWorkflow === "flux2_txt2img"` and the reducer now includes `currentJob`, `generationState`, `sessionHistory`, and `referenceFaceUrl`. | ✅ COMPLIANT |

**Compliance summary**: 7/15 scenarios fully compliant with passing runtime coverage.

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Strict workflow DTOs | ❌ Deviates | DTOs/builders are correct, and `ChatComposer.tsx` now captures raw base64. The real `flux2_editing` UI submission remains unsafe because `page.tsx` omits `editingReferenceBase64` from `handleSend` dependencies while reading it at lines 92-93. |
| Error normalization | ✅ Implemented | `normalizeError(status, body)` handles 422, 4xx/5xx envelopes, and unknown shapes. |
| WebSocket retry/backoff | ⚠️ Partial | `useGenerationJob` has `/ws/generate/{job_id}`, retry delays `[1000, 2000, 4000]`, and manual `retry()`. Runtime tests cover the pure reducer but not the hook effect, WebSocket close, timer scheduling, or actual reconnect. |
| Image proxy | ✅ Implemented | `GET /api/images/[jobId]` proxies to `{API_BASE_URL}/images/{jobId}`, streams body, preserves `Content-Type`, and handles 404. |
| Manual workflow selector | ⚠️ Partial | Aspect ratio control is replaced by workflow selector; identity and editing panels exist. UI behavior lacks component/runtime tests. |
| API integration layer `lib/api.ts` contract | ✅ Implemented | `view3/src/lib/api.ts` exists and re-exports `submitGenerate`, `getWsUrl`, `fetchImageBinary`, `normalizeError`, and `ApiError`. |
| Reducer store contract | ✅ Implemented | `StudioState` now includes `selectedWorkflow`, `currentJob`, `generationState`, `sessionHistory`, `referenceFaceUrl`, and `editingReferenceBase64`; mutations are synchronous and no `localStorage` persistence was found. |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Hooks + reducer first; no new state library | ✅ Yes | `page.tsx`, `studio-state.ts`, and `useGenerationJob` use local reducers/hooks; no external state library introduced. |
| API client in shared infrastructure with barrel/re-export satisfying `lib/api.ts` contract | ✅ Yes | Shared infrastructure exists and `src/lib/api.ts` provides the spec-required compatibility re-export. |
| Job-specific `useGenerationJob(jobId)` with embedded `wsReducer` | ⚠️ Partial | Hook and reducer exist with retry counter/backoff and terminal states. Verification remains reducer-only for reconnect success rather than hook-level runtime proof. |
| Next.js App Router image proxy route | ✅ Yes | `view3/src/app/api/images/[jobId]/route.ts` exists and is tested. |
| Page reducer handles `selectedWorkflow`, `currentJob`, `generationState`, messages/history, and error | ✅ Yes | Reducer contract now uses `sessionHistory` and syncs `generationState` from `useGenerationJob`. |

### Issues Found

**CRITICAL**

1. `flux2_editing` is still not reliably wired in the real UI submission path. `page.tsx` reads `editingReferenceBase64` in `handleSend` but the callback dependencies are `[selectedWorkflow, referenceFaceUrl]`, so after a user selects an editing image the memoized send handler can still submit with `undefined` and trigger `imageBase64 is required for flux2_editing workflow` instead of POSTing `image_base64`.
2. WebSocket reconnect success is still only proven at reducer level. The new test exercises `WS_ERROR → CONNECTING → CONNECTED → stream resumes`, but it does not instantiate `useGenerationJob`, mock `WebSocket.onclose`, advance backoff timers, and verify that the hook reconnects within 3 attempts.

**WARNING**

1. Several UI-facing spec scenarios remain static-only or reducer-only: identity panel activation, workflow selector rendering, retry button click, and panel disable after switching away.
2. `view3/test/unit-tests.sh` still emits Node `MODULE_TYPELESS_PACKAGE_JSON` warnings. The suite passes, but the warning noise should be cleaned up before CI hardening.

**SUGGESTION**

1. Add a small hook-level test for `useGenerationJob` using a mock WebSocket constructor and fake timers to prove close → backoff → reconnect → resumed message.
2. Add component/page-level tests for `ChatComposer` and `HomePage` covering `flux2_editing` image selection and submit, identity panel visibility, and retry button click.

### Verdict

**FAIL**

The requested `view3` type-check and unit tests pass, and two of the four previously critical issues are resolved (`src/lib/api.ts` and reducer `sessionHistory`/`generationState`). However, `flux2_editing` still has a real stale-callback submission defect, and WebSocket reconnect success is not proven through the actual hook/runtime path required by the spec.
