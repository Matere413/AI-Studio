# Delta for Generative AI Studio Frontend

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Realistic Persona Workflow UI Controls

The system MUST expose `realistic_persona` as a selectable workflow option in the UI. When active, the system MUST display controls for: `age` (numeric input, 18-100), `gender` (selector), `ethnicity` (selector), `wardrobe` (selector), `expression` (selector), and `background` (selector). The system MUST also display an optional reference face upload control. The system MUST NOT display model selectors, style preset menus, or technical parameter controls for persona workflows. The free-form prompt MUST remain the primary visible control.
(Previously: Displayed persona controls without reference face upload.)

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

### Requirement: Zustand Store Contract

The system MUST use `generationStore` with: `prompt` (string), `parameters` (record), `currentJob` (object: `job_id`, `status`, `progress`, `events`), `generationState` (Idle|Connecting|Generating|Done|Error), `sessionHistory` (array), `referenceFaceUrl` (string | null). Mutations synchronous. MUST NOT persist to localStorage.
(Previously: Store did not include `referenceFaceUrl` field.)

#### Scenario: Reference face URL in store

- GIVEN the user uploads a reference face image
- WHEN the upload completes
- THEN `referenceFaceUrl` is set in the store and included in generation payloads

#### Scenario: Store defaults include null reference face

- GIVEN first load
- THEN `referenceFaceUrl` is `null` alongside existing defaults
