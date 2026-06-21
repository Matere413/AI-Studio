# Generative AI Studio Frontend Specification

## Purpose

Desktop-first studio shell for configuring, submitting, monitoring, and browsing image-generation sessions. Matere design system, Zustand state, WebSocket streaming from FastAPI.

## Requirements

### Requirement: Studio Layout Composition

The system MUST render three panels: (1) Chat Sidebar (left, 320px default), (2) Workspace Canvas (center, flexible), (3) Assets Drawer (right, 280px, collapsible). Styling MUST use `ai-studio-design-system` tokens — dark surfaces, amber accents, geometric sans.

#### Scenario: Desktop layout
- GIVEN viewport >= 1280px
- THEN three panels with design-system tokens

#### Scenario: Below threshold
- GIVEN viewport < 1280px
- THEN assets drawer auto-collapses, chat narrows

### Requirement: Generation State Machine

The system MUST maintain state: `Idle` → `Booting` → `DownloadingWeights` → `Generating` → `Done` | `Error`. Transitions: `booting_server` → Booting, `downloading_weights` → DownloadingWeights, `generating`/`progress` → Generating, `completed` → Done, `error` → Error.

#### Scenario: Full lifecycle
- GIVEN Idle, valid prompt submitted
- THEN Booting → DownloadingWeights → Generating → Done

#### Scenario: Error at any stage
- GIVEN active state, `error` received
- THEN Error with message

### Requirement: WebSocket Connection and Reconnection

The system MUST connect to `/ws/generate/{job_id}` after receiving `job_id`. On disconnect before terminal event, MUST retry up to 3 times with exponential backoff (1s, 2s, 4s). After 3 failures, state MUST transition to `Error` and a Retry button MUST appear. The Retry button MUST reset the attempt counter and restart the connection.

#### Scenario: Successful stream

- GIVEN valid `job_id`, WS connects
- THEN lifecycle events received, UI updates

#### Scenario: Reconnect succeeds

- GIVEN disconnect during `Generating`, reconnect before retry limit
- THEN stream resumes without `Error`

#### Scenario: Retries exhausted

- GIVEN all 3 retries fail
- THEN `Error` with "Connection lost — please try again"

#### Scenario: Retry clicked

- GIVEN exhausted retries
- WHEN user clicks Retry
- THEN counter resets and connection restarts

### Requirement: Modal Cold Start Handling

The system MUST map `booting_server` to indeterminate "Starting server..." and `downloading_weights` to "Loading model weights...". On first `progress` >= 0, MUST switch to determinate bar.

#### Scenario: Cold start sequence
- GIVEN WS connected, no progress yet
- THEN booting → downloading → determinate on first progress

### Requirement: Form Validation and Prompt Limits

The system MUST validate: prompt NOT empty, <= 1000 chars, at least one non-whitespace char. Parameters MUST match declared workflow options. Invalid forms MUST disable Generate and show inline errors.

#### Scenario: Valid submission

- GIVEN prompt 1-1000 non-whitespace chars, valid params, Generate clicked
- THEN form submits, state -> `Connecting`

#### Scenario: Empty prompt

- GIVEN prompt empty/whitespace
- THEN Generate disabled, error "Prompt is required"

#### Scenario: Exceeds limit

- GIVEN prompt at 1000 chars
- THEN input blocked, counter "1000/1000"

#### Scenario: Invalid parameter

- GIVEN param not in declared options
- THEN inline error, Generate disabled

### Requirement: useReducer Store Contract

The reducer MUST manage `selectedWorkflow` (`"flux2_txt2img" | "flux2_editing" | "identidad_gguf"`, default `"flux2_txt2img"`), `currentJob` (object: `job_id`, `status`, `progress`, `events` | null), `generationState` (Idle|Connecting|Generating|Done|Error), `sessionHistory` (array), `referenceFaceUrl` (string | null), and `editingReferenceBase64` (string | null). Mutations remain synchronous and MUST NOT persist to localStorage.

#### Scenario: Default workflow
- GIVEN first load
- THEN `selectedWorkflow` is `"flux2_txt2img"`

#### Scenario: Completed to history

- GIVEN `completed` with `result.image_path`
- THEN appended to `sessionHistory`, `currentJob` reset

#### Scenario: Reference face URL in store

- GIVEN the user uploads a reference face image
- WHEN the upload completes
- THEN `referenceFaceUrl` is set in the store and included in generation payloads

#### Scenario: Store defaults include null reference face

- GIVEN first load
- THEN `referenceFaceUrl` is `null` alongside existing defaults

#### Scenario: Editing reference in store

- GIVEN flux2_editing is selected and a file is picked
- WHEN the file is read as base64
- THEN `editingReferenceBase64` is set in state

### Requirement: Session History Gallery

The system MUST display completed sessions below canvas: thumbnail, prompt truncated to 80 chars, timestamp. Sorted newest first. Client-side only.

#### Scenario: Populated gallery

- GIVEN 3 completions
- THEN 3 entries, thumbnails, truncated prompts, timestamps, newest first

#### Scenario: Empty gallery

- GIVEN no completions
- THEN "No generations yet" placeholder

### Requirement: API Integration Layer

`lib/api.ts` MUST provide `submitGenerate(request)` POSTing `/api/generate` with the strict DTO and returning `{ job_id, status }` or `{ error: { code, detail } }`. `getWsUrl(job_id)` MUST return the WS URL.

#### Scenario: Submit with strict DTO

- GIVEN valid discriminated request
- WHEN `submitGenerate` called
- THEN POST returns `{ job_id, status }`

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

### Requirement: Prompt-First Product Controls

The system MUST keep the free-form prompt as the primary visible control for product premium workflow submissions. The system MUST NOT display closed style preset menus, model selectors, or technical parameter controls for product workflows. The format selector (square/vertical) MAY be exposed as a simple toggle.

#### Scenario: Prompt-first product submission

- GIVEN the user selects product premium workflow
- WHEN the UI renders
- THEN only a prompt input and optional format toggle are visible

#### Scenario: No style preset menu shown

- GIVEN the product premium workflow is active
- WHEN the UI renders
- THEN no style preset menu or model selector is displayed

#### Scenario: Format toggle changes output

- GIVEN the user toggles format from square to vertical
- WHEN the user submits the generation
- THEN the request includes `format = "vertical"`

### Requirement: Behavior Preservation Contract

The system MUST satisfy all existing requirements in `generative-ai-studio-frontend` and `image-generation` specs after the folder restructure. No product-visible behavior, API contract, WebSocket protocol, or user-facing interaction SHALL change.

#### Scenario: Generation submission unchanged

- GIVEN valid prompt and parameters, user clicks Generate
- THEN POST `/api/generate` is called with identical payload as before restructure

#### Scenario: WebSocket lifecycle unchanged

- GIVEN a `job_id` is received
- THEN WS connection to `/api/ws/generate/{job_id}` follows the same connect/retry/exhaust flow

#### Scenario: Image preview unchanged

- GIVEN a completed job with `result.image_path`
- THEN image loads from `/api/images/{job_id}` via `next/image` as before

#### Scenario: State machine transitions unchanged

- GIVEN any WebSocket event or user action
- THEN state transitions (`Idle` → `Connecting` → `Generating` → `Done` | `Error`) remain identical

#### Scenario: Store contract unchanged

- GIVEN the app loads or a generation completes
- THEN `generationStore` shape, mutations, and `sessionHistory` behavior are unchanged

#### Scenario: Form validation unchanged

- GIVEN empty, whitespace-only, or >1000-char prompt
- THEN Generate is disabled with the same inline errors as before

#### Scenario: Session history gallery unchanged

- GIVEN multiple completed generations
- THEN gallery displays thumbnails, truncated prompts, timestamps sorted newest-first

### Requirement: Realistic Persona Workflow UI Controls

The system MUST expose `realistic_persona` as a selectable workflow option in the UI. When active, the system MUST display controls for: `age` (numeric input, 18-100), `gender` (selector), `ethnicity` (selector), `wardrobe` (selector), `expression` (selector), and `background` (selector). The system MUST also display an optional reference face upload control. The system MUST NOT display model selectors, style preset menus, or technical parameter controls for persona workflows. The free-form prompt MUST remain the primary visible control.

#### Scenario: Persona workflow selection

- GIVEN the user selects `realistic_persona` workflow
- WHEN the UI renders
- THEN persona controls, prompt input, and optional reference face upload are visible

#### Scenario: Persona controls submit correctly

- GIVEN the user fills age, gender, wardrobe, uploads a reference face, and enters a prompt
- WHEN the user submits the generation
- THEN the request includes all filled persona controls and the reference face URL

#### Scenario: No technical controls shown

- GIVEN the `realistic_persona` workflow is active
- WHEN the UI renders
- THEN no model selector, CFG slider, sampler selector, or step count is displayed

### Requirement: Optional Reference Face Upload

The system MUST provide an optional reference face image upload control when `realistic_persona` workflow is active. The uploaded image MUST be stored in frontend session state (Zustand store) and its URL MUST be included in subsequent generation requests. The upload MUST NOT be required — generation MUST proceed normally without it using prompt-only fallback.

#### Scenario: Reference face upload visible for persona workflow

- GIVEN the user has `realistic_persona` workflow selected
- WHEN the UI renders
- THEN an optional reference face upload control is visible alongside persona controls

#### Scenario: Upload stores URL in session state

- GIVEN the user uploads a valid image file
- WHEN the upload completes
- THEN the image URL is stored in the Zustand store and persists across generations

#### Scenario: Generation without reference face

- GIVEN no reference face image has been uploaded
- WHEN the user submits a `realistic_persona` generation
- THEN the request is sent without `image_url` and proceeds as prompt-only generation

#### Scenario: Generation with reference face

- GIVEN a reference face image has been uploaded and stored
- WHEN the user submits a `realistic_persona` generation
- THEN the request includes the stored `image_url` for FaceID conditioning

#### Scenario: Reference face reused without re-upload

- GIVEN a reference face image was uploaded for a previous generation
- WHEN the user submits another `realistic_persona` generation
- THEN the stored URL is reused without requiring re-upload

### Requirement: Reference Face Removal

The system MUST allow the user to remove a previously uploaded reference face image. When removed, the URL MUST be cleared from session state and subsequent generations MUST use prompt-only fallback.

#### Scenario: Remove uploaded reference face

- GIVEN a reference face image is currently stored in session state
- WHEN the user clicks the remove/clear button
- THEN the URL is cleared from the Zustand store

#### Scenario: Generation after removal uses prompt-only

- GIVEN the reference face was removed from session state
- WHEN the user submits a `realistic_persona` generation
- THEN the request is sent without `image_url` and uses prompt-only generation

### Requirement: Reference Face Upload Validation

The system MUST validate uploaded reference face images: accepted formats MUST include PNG and JPEG, maximum file size MUST be 10MB. Invalid files MUST be rejected with an inline error message. The upload control MUST indicate upload progress.

#### Scenario: Valid image accepted

- GIVEN the user selects a PNG or JPEG file under 10MB
- WHEN the upload is initiated
- THEN the upload succeeds and the URL is stored

#### Scenario: Invalid format rejected

- GIVEN the user selects a non-image file (e.g., PDF, GIF)
- WHEN the upload is attempted
- THEN an inline error "Only PNG and JPEG images are accepted" is displayed

#### Scenario: File too large rejected

- GIVEN the user selects an image file larger than 10MB
- WHEN the upload is attempted
- THEN an inline error "Image must be under 10MB" is displayed

### Requirement: Identity GGUF Workflow Selection

The system MUST expose `identidad_gguf` as a selectable workflow. When active, the system MUST display the lateral identity panel and require both prompt and reference image before submission.

#### Scenario: Identity workflow selected

- GIVEN the user selects `identidad_gguf`
- WHEN the UI renders
- THEN the lateral identity panel is visible and active

#### Scenario: Switching away disables panel

- GIVEN the user switches from `identidad_gguf` to another workflow
- WHEN the UI renders
- THEN the identity panel shows the disabled state with warning copy

### Requirement: Custom Reference Image Upload with Validation

The system MUST allow uploading a reference image via file picker. Accepted formats: PNG, JPEG. Maximum size: 5MB. Files between 5MB–10MB MUST be auto-compressed. Files over 10MB or failed compression MUST be rejected with inline error. No crop tool is present.

#### Scenario: Valid image under limit accepted

- GIVEN a PNG or JPEG file under 5MB is selected
- WHEN the upload completes
- THEN the image URL is stored in `generationStore` and displayed in preview

#### Scenario: File over 5MB auto-compressed

- GIVEN a JPEG file between 5MB and 10MB is selected
- WHEN the upload is initiated
- THEN the system compresses the image to under 5MB and stores the result

#### Scenario: File over 10MB rejected

- GIVEN an image file exceeding 10MB is selected
- WHEN the upload is attempted
- THEN an inline error "Image must be under 10MB after compression" is displayed

### Requirement: Identity Gallery Selection

The system MUST display a gallery of previously uploaded reference images when the identity panel is active. Selecting a thumbnail MUST set it as the current reference. Gallery persists only for the current session.

#### Scenario: Gallery image selected

- GIVEN the panel is active and gallery contains images
- WHEN the user clicks a thumbnail
- THEN that image becomes the current reference and preview updates

#### Scenario: Empty gallery

- GIVEN no reference images uploaded this session
- WHEN the gallery renders
- THEN a "No reference images yet" placeholder is displayed

### Requirement: Identity-Aware Form Validation

The system MUST disable Generate for `identidad_gguf` when prompt is empty/whitespace OR no reference image is selected, with inline errors indicating missing fields.

#### Scenario: Missing reference blocks submission

- GIVEN `identidad_gguf` active with valid prompt but no reference image
- WHEN the user attempts to submit
- THEN Generate is disabled with error "Reference image is required"

#### Scenario: Both fields present enables submission

- GIVEN `identidad_gguf` active with valid prompt and reference image
- WHEN the UI renders
- THEN Generate button is enabled

### Requirement: Identity Payload in Generation Request

The system MUST include `image_url` in the POST body ONLY when `workflow = "identidad_gguf"` and a reference image is selected. For all other workflows, `image_url` MUST NOT be included.

#### Scenario: Identity payload includes image_url

- GIVEN `identidad_gguf` with a stored reference image
- WHEN the user submits
- THEN the POST body includes `image_url` with the stored value

#### Scenario: Non-identity workflow excludes image_url

- GIVEN a non-identity workflow with a stored reference image
- WHEN the user submits
- THEN the POST body does NOT include `image_url`

### Requirement: Chat Sidebar

The system MUST provide a chat sidebar with: scrollable message history (top), prompt input bar (bottom), manual workflow dropdown, and speed selector. Submission via Enter or send button.

#### Scenario: Prompt submission
- GIVEN valid prompt, workflow selected, user presses Enter
- THEN message appended to history, generation dispatched

#### Scenario: Empty prompt blocked
- GIVEN prompt empty/whitespace
- THEN send disabled, inline error "Prompt is required"

### Requirement: Manual Workflow Selector

The system MUST replace the Aspect Ratio control with a Workflow Selector for `flux2_txt2img`, `flux2_editing`, `identidad_gguf`. Default MUST be `flux2_txt2img`. Selection MUST update the store's `selectedWorkflow`, reset workflow-specific params, and toggle the identity reference panel.

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

#### Scenario: Identity requires reference
- GIVEN `identidad_gguf` selected, no reference in assets
- THEN Generate disabled, error "Reference image required"

### Requirement: Workspace Canvas

The system MUST display generated images as a working artboard. During generation, MUST show progress. On `completed`, MUST render result at native resolution.

#### Scenario: Image completion
- GIVEN `completed` with `result.image_path`
- THEN image renders on canvas

#### Scenario: Progress during generation
- GIVEN `progress` with numeric value
- THEN progress indicator updates

### Requirement: Assets Drawer

The system MUST provide a collapsible right panel for reference image/mask upload and management. Accepts PNG/JPEG (max 10MB). Displays thumbnails, supports removal.

#### Scenario: Upload reference
- GIVEN valid PNG < 10MB, upload completes
- THEN thumbnail in assets list, URL in store

#### Scenario: Remove asset
- GIVEN thumbnail visible, user clicks remove
- THEN asset removed, store cleared

### Requirement: Design System Token Contract

All components MUST use `ai-studio-design-system` classes. Dark surfaces (`--bg-0` to `--bg-3`), amber accents (`--accent`), cream text (`--fg-1`), geometric sans body, monospace labels. MUST NOT contain retro pixel-art, CRT scanlines, or VT323.

#### Scenario: Token compliance
- GIVEN any component renders
- THEN uses design-system classes, zero retro residuals

### Requirement: Backend Event Type Alignment

WebSocket events MUST align with backend enum: `booting_server`, `downloading_weights`, `generating`, `progress`, `completed`, `error`. Each MUST drive corresponding UI state.

#### Scenario: Boot sequence
- GIVEN `booting_server` received
- THEN "Starting server..." with indeterminate progress

#### Scenario: Weight download
- GIVEN `downloading_weights` received
- THEN "Loading model weights..." status

#### Scenario: Generation progress
- GIVEN `progress` with numeric value
- THEN determinate bar updates
