# Delta Spec: view3-api-integration

## Domain: generative-ai-studio-frontend

Connects facade-only studio to live API; consumes backend contracts as specified.

## ADDED Requirements

### Requirement: Strict HTTP Client for POST /api/generate

The client MUST build `workflow_name` discriminated bodies. `flux2_txt2img` sends `prompt` and optional `use_turbo` boolean, MUST NOT send `seed`. `flux2_editing` sends `prompt`, `image_base64`, and optional `use_turbo`; it MUST NOT send `width`/`height` or `seed`. `identidad_gguf` sends `prompt`, `image_url`, and optional `width`, `height`, and `seed`. Legacy fields MUST NOT be sent.

#### Scenario: Flux 2 txt2img
- GIVEN `flux2_txt2img` selected
- WHEN submitted
- THEN body has `workflow_name`, `prompt`, `use_turbo` boolean

#### Scenario: Flux 2 editing
- GIVEN `flux2_editing` selected with reference image
- WHEN submitted
- THEN body includes `image_base64`, excludes `width`/`height`

#### Scenario: Identity GGUF
- GIVEN `identidad_gguf` selected with reference URL
- WHEN submitted
- THEN body includes `image_url`

### Requirement: Typed Error Envelope Handling

The client MUST normalize 422 (`detail`) and 400/500 (`{ error: { code, detail } }`) responses into `{ code, detail }`. Unknown shapes MUST fall back to `{ code: "unknown_error", detail: "Request failed" }`.

#### Scenario: Validation error
- GIVEN HTTP 422 with `detail`
- WHEN parsed
- THEN UI receives `{ code: "validation_error", detail }`

#### Scenario: Operational error
- GIVEN HTTP 500 with `{ error: { code, detail } }`
- WHEN parsed
- THEN UI receives the same `code` and `detail`

### Requirement: WebSocket Resilience with Retry Button

The WS hook MUST connect to `/ws/generate/{job_id}`. On non-terminal disconnect, it MUST retry up to 3 times with backoff 1s/2s/4s. After exhaustion, state MUST become `Error` and a Retry button MUST reset attempts and reconnect.

#### Scenario: Reconnect succeeds
- GIVEN disconnect during generation
- WHEN retry connects within 3 attempts
- THEN stream resumes

#### Scenario: Retries exhausted
- GIVEN 3 reconnect failures
- THEN state is `Error` and Retry button appears

#### Scenario: Retry clicked
- GIVEN exhausted retries
- WHEN user clicks Retry
- THEN counter resets and connection restarts

### Requirement: Next.js Image Proxy

The app MUST expose `GET /api/images/[jobId]` proxying to `{API_BASE_URL}/images/{job_id}` and streaming the binary with upstream `Content-Type`. Upstream 404 MUST return 404 with `{ code, detail }`. Canvas MUST load images through the proxy.

#### Scenario: Proxy serves image
- GIVEN completed job
- WHEN canvas requests `/api/images/{job_id}`
- THEN route returns image binary with correct `Content-Type`

#### Scenario: Proxy upstream 404
- GIVEN unknown `job_id`
- WHEN proxy calls backend
- THEN returns 404 with `{ code, detail }`

## MODIFIED Requirements

### Requirement: Manual Workflow Selector

The system MUST replace the Aspect Ratio control with a Workflow Selector for `flux2_txt2img`, `flux2_editing`, `identidad_gguf`. Default MUST be `flux2_txt2img`. Selection MUST update `generationStore.selectedWorkflow`, reset workflow-specific params, and toggle the identity reference panel.
(Previously: dropdown updated `selectedWorkflow` and adapted UI only.)

#### Scenario: Workflow selection
- GIVEN selector renders
- WHEN user selects `flux2_editing`
- THEN `selectedWorkflow` updates, Aspect Ratio hidden, editing controls shown

#### Scenario: Identity workflow activates panel
- GIVEN user selects `identidad_gguf`
- WHEN UI renders
- THEN identity reference panel becomes active

#### Scenario: Switching away resets params
- GIVEN `identidad_gguf` active with reference image
- WHEN user switches to `flux2_txt2img`
- THEN workflow-specific params reset and identity panel disables

### Requirement: API Integration Layer

`lib/api.ts` MUST provide `submitGenerate(request)` POSTing `/api/generate` with the strict DTO and returning `{ job_id, status }` or `{ error: { code, detail } }`. `getWsUrl(job_id)` MUST return the WS URL.
(Previously: accepted loose prompt/params and returned mock data.)

#### Scenario: Submit with strict DTO
- GIVEN valid discriminated request
- WHEN `submitGenerate` called
- THEN POST returns `{ job_id, status }`

### Requirement: useReducer Store Contract

The reducer MUST manage `selectedWorkflow` (`"flux2_txt2img" | "flux2_editing" | "identidad_gguf"`, default `"flux2_txt2img"`). It MUST keep `currentJob`, `generationState`, `sessionHistory`, and `referenceFaceUrl`. Mutations remain synchronous and MUST NOT persist to `localStorage`.
(Previously: no `selectedWorkflow` state.)

#### Scenario: Default workflow
- GIVEN first load
- THEN `selectedWorkflow` is `"flux2_txt2img"`
