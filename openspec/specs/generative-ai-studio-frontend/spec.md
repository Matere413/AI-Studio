# Generative AI Studio Frontend Specification

## Purpose

Desktop-first studio shell for configuring, submitting, monitoring, and browsing image-generation sessions. Matere design system, Zustand state, WebSocket streaming from FastAPI.

## Requirements

### Requirement: Studio Layout Composition

The system MUST render: (1) 340px fixed input sidebar, (2) main output canvas filling remaining space, (3) collapsible terminal log overlay. Styling MUST use Matere tokens, local fonts, chunky borders, CRT aesthetic, `VT323` for terminal text.

#### Scenario: Desktop layout

- GIVEN viewport >= 1024px, page loads
- THEN 340px sidebar left, canvas fills rest, terminal collapsed

#### Scenario: Below threshold

- GIVEN viewport < 1024px, page loads
- THEN layout stacks vertically

### Requirement: Generation State Machine

The system MUST maintain state: `Idle` -> `Connecting` -> `Generating` -> `Done` | `Error`. UI MUST reflect state via progress bar, status text, terminal. Transitions driven by WebSocket events or user actions only.

#### Scenario: Full lifecycle

- GIVEN `Idle` with valid prompt, user clicks Generate
- THEN `Connecting` -> `Generating` (WS connected) -> `Done` (`completed` event)

#### Scenario: Failure

- GIVEN `Generating`, server sends `error` event
- THEN `Error` state with message displayed

#### Scenario: Cancel

- GIVEN `Connecting`, user clicks Cancel
- THEN `Idle`, WebSocket aborted

### Requirement: WebSocket Connection and Reconnection

The system MUST connect to `/api/ws/generate/{job_id}` after receiving `job_id`. On disconnect before terminal event, MUST retry up to 3 times with exponential backoff (1s, 2s, 4s). After 3 failures, MUST transition to `Error`.

#### Scenario: Successful stream

- GIVEN valid `job_id`, WS connects
- THEN lifecycle events received, UI updates

#### Scenario: Reconnect succeeds

- GIVEN disconnect during `Generating`, reconnect before retry limit
- THEN stream resumes without `Error`

#### Scenario: Retries exhausted

- GIVEN all 3 retries fail
- THEN `Error` with "Connection lost — please try again"

### Requirement: Modal Cold Start Handling

The system MUST show indeterminate progress + terminal "Starting generation server..." before first numeric `progress`. On `progress` >= 0, MUST switch to determinate pixel bar.

#### Scenario: Cold start delay

- GIVEN no `progress` after 2s
- THEN indeterminate progress with "Starting generation server..."

#### Scenario: Becomes determinate

- GIVEN indeterminate showing, event has `progress` >= 0
- THEN pixel bar shows percentage

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

### Requirement: Zustand Store Contract

The system MUST use `generationStore` with: `prompt` (string), `parameters` (record), `currentJob` (object: `job_id`, `status`, `progress`, `events`), `generationState` (Idle|Connecting|Generating|Done|Error), `sessionHistory` (array), `referenceFaceUrl` (string | null). Mutations synchronous. MUST NOT persist to localStorage.

#### Scenario: Defaults

- GIVEN first load
- THEN `prompt`="", `parameters`={}, `currentJob`=null, `generationState`=`Idle`, `sessionHistory`=[], `referenceFaceUrl`=null

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

### Requirement: Session History Gallery

The system MUST display completed sessions below canvas: thumbnail, prompt truncated to 80 chars, timestamp. Sorted newest first. Client-side only.

#### Scenario: Populated gallery

- GIVEN 3 completions
- THEN 3 entries, thumbnails, truncated prompts, timestamps, newest first

#### Scenario: Empty gallery

- GIVEN no completions
- THEN "No generations yet" placeholder

### Requirement: API Integration Layer

`lib/api.ts` MUST provide: `submitGenerate(prompt, params)` POSTing `/api/generate` returning `{ job_id, status }`, `getWsUrl(job_id)` returning WS URL. `next.config.ts` MUST proxy `/api/*` to FastAPI in dev.

#### Scenario: Submit

- GIVEN valid input, `submitGenerate` called
- THEN POST `/api/generate` returns `job_id` + `status = "pending"`

#### Scenario: WS URL

- GIVEN `getWsUrl("abc-123")`
- THEN returns `/api/ws/generate/abc-123`

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
