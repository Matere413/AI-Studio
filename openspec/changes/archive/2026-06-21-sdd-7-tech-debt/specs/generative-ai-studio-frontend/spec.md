# Delta for Generative AI Studio Frontend

## MODIFIED Requirements

### Requirement: useReducer Store Contract

The reducer MUST manage `selectedWorkflow` (`"flux2_txt2img" | "flux2_editing" | "identidad_gguf"`, default `"flux2_txt2img"`), `currentJob` (object: `job_id`, `status`, `progress`, `events` | null), `generationState` (Idle|Connecting|Generating|Done|Error), `sessionHistory` (array), `referenceFaceUrl` (string | null), and `editingReferenceBase64` (string | null). Mutations remain synchronous and MUST NOT persist to localStorage. On `completed`, the frontend MUST derive the image URL from `job_id` and MUST NOT rely on `result.image_path`.
(Previously: `completed` event stored `result.image_path` in session history.)

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

### Requirement: Workspace Canvas

The system MUST display generated images as a working artboard. During generation, MUST show progress. On `completed`, MUST render result at native resolution using `GET /api/images/{job_id}`.
(Previously: rendering could use `result.image_path` from the WebSocket event.)

#### Scenario: Image completion

- GIVEN `completed` with `job_id`
- THEN image renders on canvas from `/api/images/{job_id}`

#### Scenario: Progress during generation

- GIVEN `progress` with numeric value
- THEN progress indicator updates

### Requirement: Behavior Preservation Contract

The system MUST satisfy all existing requirements in `generative-ai-studio-frontend` and `image-generation` specs after the folder restructure. No product-visible behavior, API contract, WebSocket protocol, or user-facing interaction SHALL change, except that image URLs are derived from `job_id` and `result.image_path` is no longer consumed.
(Previously: `result.image_path` was part of the contract.)

#### Scenario: Image preview unchanged

- GIVEN a completed job
- THEN image loads from `/api/images/{job_id}` via `next/image`

#### Scenario: Store contract unchanged

- GIVEN the app loads or a generation completes
- THEN `generationStore` shape, mutations, and `sessionHistory` behavior are unchanged except for `image_path` removal

## REMOVED Requirements

### Requirement: Completed event stores `result.image_path`

(Reason: Absolute paths leak server internals and duplicate the canonical `GET /images/{job_id}` resource.)
(Migration: Update any tests and store reducers to derive image URLs from `job_id`.)
