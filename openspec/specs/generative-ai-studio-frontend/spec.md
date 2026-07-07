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

The reducer MUST manage `selectedWorkflow` (`"flux2_txt2img" | "flux2_editing" | "identidad_gguf"`, default `"flux2_txt2img"`), `currentJob` (object: `job_id`, `status`, `progress`, `events` | null), `generationState` (Idle|Connecting|Generating|Done|Error), `sessionHistory` (array), `referenceFaceUrl` (string | null), `editingReferenceBase64` (string | null), and `uploadStatus` (UploadStatus). The reducer MUST NOT store asset images as `dataUrl`. Mutations remain synchronous and MUST NOT persist to localStorage. On `completed`, the frontend MUST derive the image URL from `job_id` and MUST NOT rely on `result.image_path`.
(Previously: `completed` event stored `result.image_path` in session history; the store included `dataUrl` for assets.)

#### Scenario: Default workflow
- GIVEN first load
- THEN `selectedWorkflow` is `"flux2_txt2img"`

#### Scenario: Completed to history

- GIVEN `completed` with `job_id`
- THEN appended to `sessionHistory` with image URL derived from `job_id`, `currentJob` reset

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

#### Scenario: Store has no dataUrl

- GIVEN the app loads
- WHEN inspecting the store shape
- THEN no `dataUrl` field exists

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

The system MUST satisfy all existing requirements in `generative-ai-studio-frontend` and `image-generation` specs after the folder restructure. No product-visible behavior, API contract, WebSocket protocol, or user-facing interaction SHALL change, except that image URLs are derived from `job_id` and `result.image_path` is no longer consumed.
(Previously: `result.image_path` was part of the contract.)

#### Scenario: Generation submission unchanged

- GIVEN valid prompt and parameters, user clicks Generate
- THEN POST `/api/generate` is called with identical payload as before restructure

#### Scenario: WebSocket lifecycle unchanged

- GIVEN a `job_id` is received
- THEN WS connection to `/api/ws/generate/{job_id}` follows the same connect/retry/exhaust flow

#### Scenario: Image preview unchanged

- GIVEN a completed job
- THEN image loads from `/api/images/{job_id}` via `next/image`

#### Scenario: State machine transitions unchanged

- GIVEN any WebSocket event or user action
- THEN state transitions (`Idle` → `Connecting` → `Generating` → `Done` | `Error`) remain identical

#### Scenario: Store contract unchanged

- GIVEN the app loads or a generation completes
- THEN `generationStore` shape, mutations, and `sessionHistory` behavior are unchanged except for `image_path` removal

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

The system MUST compress uploaded reference images to WebP ≤1024×1024 before requesting a presigned upload. Accepted source formats include PNG and JPEG.
(Previously: files were auto-compressed to JPEG/PNG, not WebP.)

#### Scenario: Reference compressed to WebP

- GIVEN a JPEG file between 5MB and 10MB
- WHEN selected as reference
- THEN it is compressed to WebP ≤1024×1024 and uploaded to R2

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

### Requirement: Prompt-First Agent Submission

The system MUST make the chat prompt the primary submission control and SHALL send orchestration requests without requiring users to choose a technical workflow. Advanced manual workflow controls SHOULD NOT be visible in the default designer-facing path.

#### Scenario: Natural language request submitted

- GIVEN the user enters a prompt and optionally selects assets
- WHEN the user submits from the chat sidebar
- THEN the client sends an orchestration request with prompt and asset identifiers
- AND does not send stale manual workflow fields

#### Scenario: Designer-facing UI remains simple

- GIVEN the default studio experience renders
- WHEN no advanced mode is enabled
- THEN workflow selectors, model selectors, CFG, sampler, and raw parameter controls are hidden

### Requirement: Agent Stage Timeline

The system MUST show visible orchestration stages before the final image, including planning, validating assets, dispatching, generating, and completed or blocked states.

#### Scenario: Successful staged execution

- GIVEN an orchestration request is submitted
- WHEN the backend accepts and dispatches a job
- THEN the UI displays planning, validation, dispatch, and generation stages
- AND continues to use WebSocket lifecycle updates for execution progress

#### Scenario: Clarification stage

- GIVEN the backend returns a clarifying question
- WHEN the response is rendered
- THEN the timeline shows the request blocked at planning
- AND the question is displayed as the next user action

#### Scenario: Missing asset stage

- GIVEN the backend returns missing-asset guidance
- WHEN the response is rendered
- THEN the timeline shows the request blocked at asset validation
- AND the UI suggests uploading or selecting the required asset role

### Requirement: Orchestration Client Contract

The client MUST normalize orchestration outcomes into one of: `job_started`, `clarification_required`, `missing_asset`, or `error`. It MUST remove deprecated `identidad_gguf` assumptions from the default prompt-first request builder.

#### Scenario: Job outcome normalized

- GIVEN the backend returns `job_id` and `status = pending`
- WHEN the client parses the response
- THEN UI state transitions into execution monitoring

#### Scenario: Deprecated contract not sent

- GIVEN a user asks for identity/persona preservation
- WHEN the client submits the orchestration request
- THEN it sends selected asset identifiers and prompt context
- AND it MUST NOT require or send `identidad_gguf` as a manual workflow choice

### Requirement: Chat Sidebar

The system MUST provide a chat sidebar with scrollable message history at the top, a prompt input bar at the bottom, selected-asset context, and submission via Enter or send button. The default sidebar MUST NOT require a manual workflow dropdown before submission.
(Previously: The chat sidebar included a manual workflow dropdown and speed selector as default controls.)

#### Scenario: Prompt submission
- GIVEN a valid prompt and optional selected assets
- WHEN the user presses Enter or the send button
- THEN the message is appended to history and an orchestration request is dispatched

#### Scenario: Empty prompt blocked
- GIVEN prompt empty/whitespace
- THEN send is disabled with inline error "Prompt is required"


### Requirement: Workspace Canvas

The system MUST display generated images as a working artboard. During generation, MUST show progress. On `completed`, MUST render result at native resolution using `GET /api/images/{job_id}`.
(Previously: rendering could use `result.image_path` from the WebSocket event.)

#### Scenario: Image completion
- GIVEN `completed` with `job_id`
- THEN image renders on canvas from `/api/images/{job_id}`

#### Scenario: Progress during generation
- GIVEN `progress` with numeric value
- THEN progress indicator updates

### Requirement: Assets Drawer

The system MUST render R2-backed assets in the right drawer with an upload state machine and retry UX, replacing `dataUrl` storage.
(Previously: assets were stored as `dataUrl`.)

#### Scenario: Upload compressed WebP
- GIVEN a valid image selected
- WHEN compression and presigned upload succeed
- THEN the drawer shows a thumbnail backed by an R2 URL

#### Scenario: Upload failure with retry
- GIVEN a presigned upload fails
- WHEN the error is shown
- THEN a Retry button re-requests the presigned URL and retries upload

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

### Requirement: Auth Feature Module

The frontend MUST add a `features/auth/` feature with hexagonal structure: `domain/` (`AuthUser`, `AuthSession` types), `application/` (`useAuth`, `useRequireVerified` hooks), `infrastructure/` (auth API client wrapping `fetchWithSession` with `credentials: "include"`), and `presentation/` (`RegisterForm`, `LoginForm`, `VerifyEmailPage`, `SaveCTA`, `VerificationBanner`). The anonymous `X-Session-ID` path in `fetchWithSession` MUST remain unchanged for generation requests.

#### Scenario: Auth feature structure exists

- GIVEN the frontend codebase
- WHEN the structure is inspected
- THEN `features/auth/{domain,application,infrastructure,presentation}` directories exist

#### Scenario: Anonymous generation path unchanged

- GIVEN an anonymous visitor
- WHEN the visitor generates an image
- THEN `fetchWithSession` still sends `X-Session-ID` and no credentials for generation requests

### Requirement: AuthProvider and useAuth Hook

An `AuthProvider` MUST wrap the root layout. A `useAuth()` hook MUST expose `{user, isAuthenticated, isVerified, login, register, logout, logoutGlobal}`. On mount it MUST call `GET /auth/me` to hydrate state; failure to hydrate MUST leave the user as anonymous (no error UI).

#### Scenario: Hydrate on mount

- GIVEN a logged-in user reloads the page
- WHEN the app mounts
- THEN `useAuth` calls GET /auth/me and `user` is populated

#### Scenario: Anonymous stays anonymous

- GIVEN a visitor with no auth cookies
- WHEN the app mounts
- THEN `user` is `null` and `isAuthenticated` is `false` (no error UI)

### Requirement: Route Guard Middleware

`middleware.ts` MUST protect `/login`, `/register`, `/verify-email` routes. The guard MUST only check cookie presence (no JWT verification at the edge). Studio and generation routes MUST remain public. Authenticated users visiting `/login` or `/register` MUST be redirected to `/`.

#### Scenario: Anonymous can reach login

- GIVEN a visitor with no auth cookies
- WHEN navigating to /login
- THEN the page renders

#### Scenario: Authenticated redirected away from login

- GIVEN a user with auth cookies
- WHEN navigating to /login
- THEN redirected to `/`

#### Scenario: Studio stays public

- GIVEN any visitor (anonymous or authenticated)
- WHEN navigating to the studio
- THEN no redirect occurs

### Requirement: Login and Register Forms

`presentation/components/` MUST include `LoginForm` and `RegisterForm` posting to `/auth/login` and `/auth/register` respectively, with `credentials: "include"`. Forms MUST show inline validation errors matching backend codes (`weak_password`, `email_taken`, `invalid_credentials`). On success the user MUST be redirected to the `next` query param or `/` (no onboarding screen).

#### Scenario: Register redirects to studio

- GIVEN a valid registration
- WHEN the form succeeds
- THEN the user lands on `/` (Studio), no onboarding step

#### Scenario: Inline error mapping

- GIVEN a 409 `email_taken` from backend
- WHEN the form renders the error
- THEN the email field shows "Email already registered"

### Requirement: Email Verification Banner

A yellow `VerificationBanner` (using `#eab208` per DESIGN.md) MUST render in the top bar when `isAuthenticated && !isVerified`. It MUST link to resend verification and MUST NOT block generation. It MUST disappear once `email_verified=TRUE`.

#### Scenario: Banner shown when unverified

- GIVEN an authenticated user with `email_verified=FALSE`
- WHEN the studio renders
- THEN a yellow banner appears in the top bar with a resend link

#### Scenario: Banner hidden when verified

- GIVEN an authenticated user with `email_verified=TRUE`
- WHEN the studio renders
- THEN no banner is shown

### Requirement: Save CTA Auth Gating

The Save CTA MUST be visible only when authenticated. When an anonymous user attempts to save, the UI MUST redirect to `/login?next=<currentPath>`. When an authenticated but unverified user attempts to save, the UI MUST show the verification banner and NOT call the save endpoint (preempt the `403`).

#### Scenario: Anonymous save redirects to login

- GIVEN an anonymous user clicks Save
- WHEN the CTA handler runs
- THEN the user is redirected to `/login?next=<currentPath>`

#### Scenario: Verified user saves

- GIVEN an authenticated verified user
- WHEN the user clicks Save
- THEN POST /projects is called with credentials and succeeds

#### Scenario: Unverified user blocked preemptively

- GIVEN an authenticated but unverified user
- WHEN the user clicks Save
- THEN the banner is emphasized and the save endpoint is NOT called (no 403 round-trip)

### Requirement: Auth-Aware API Client

`fetchWithSession` MUST send `credentials: "include"` on all requests so auth cookies flow. The anonymous `X-Session-ID` header MUST still be attached for generation requests. Authenticated endpoints MUST rely on cookies only (no manual Authorization header).

#### Scenario: Credentials included

- GIVEN any fetch via `fetchWithSession`
- WHEN the request is built
- THEN `credentials: "include"` is set

#### Scenario: Refresh rotation transparent

- GIVEN a request fails with 401 due to expired access token
- WHEN the client detects a valid refresh cookie
- THEN it calls /auth/refresh transparently and retries the original request once
