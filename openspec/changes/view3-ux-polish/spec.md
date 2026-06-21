# view3-ux-polish Delta

## Domain: generative-ai-studio-frontend

### ADDED Requirements

#### Requirement: Generation Input Gating
The system MUST enable composer, workflow selector, and attach controls when `currentJob` is null; disable them while a job is active.

##### Scenario: Input gating
- GIVEN `currentJob` is null
- WHEN a job starts
- THEN controls disable
- AND WHEN the job ends
- THEN controls enable

#### Requirement: Dynamic Status Derivation
The system MUST derive `displayedStatus` from `currentJob`.

##### Scenario: Status follows job state
- GIVEN `currentJob` is null
- WHEN a job starts with status `generating`
- THEN status changes from idle to "GENERATING..."

#### Requirement: Turbo Speed Selector
The system MUST expose a Turbo/Balanced selector for Flux workflows, hide it for `identidad_gguf`, and include `use_turbo` only in Flux payloads.

##### Scenario: Flux shows Turbo, identity hides it
- GIVEN Turbo is selected
- WHEN selecting and submitting `flux2_txt2img` and `identidad_gguf`
- THEN selector is visible and payload includes `use_turbo` for flux
- AND selector is hidden and payload excludes `use_turbo` for identity

#### Requirement: Session-Local Asset Upload
The system MUST replace `MOCK_ASSETS` with reducer-backed `sessionAssets` from local file Data URIs.

##### Scenario: Upload to session
- GIVEN the user selects a PNG file
- WHEN the file is read
- THEN a Data URI is appended to `sessionAssets` and shown in the drawer

### MODIFIED Requirements

#### Requirement: Workspace Canvas
The system MUST display generated images as a working artboard, show progress during generation, render results at native resolution, and hide the idle frame when no job exists.
(Previously: rendered an idle waiting frame when no job was active.)

##### Scenario: Idle frame hidden
- GIVEN `currentJob` is null
- WHEN the canvas renders
- THEN no idle waiting frame is displayed

##### Scenario: Image completion
- GIVEN `completed` with `result.image_path`
- THEN image renders on canvas

##### Scenario: Progress during generation
- GIVEN `progress` with numeric value
- THEN progress indicator updates

#### Requirement: Assets Drawer
The system MUST provide a collapsible right panel for reference image/mask upload and management; accept PNG/JPEG (max 10MB), display thumbnails, support removal, render `sessionAssets`, and allow local file upload.
(Previously: rendered `MOCK_ASSETS` and upload was a no-op.)

##### Scenario: No mock data
- GIVEN the drawer renders
- THEN it displays `sessionAssets`, not `MOCK_ASSETS`

##### Scenario: File picker opens
- GIVEN the user clicks upload
- THEN a native file picker is presented

##### Scenario: Upload reference
- GIVEN valid PNG < 10MB, upload completes
- THEN thumbnail in assets list, URL in store

##### Scenario: Remove asset
- GIVEN thumbnail visible, user clicks remove
- THEN asset removed, store cleared

## Domain: app-shell

### ADDED Requirements

#### Requirement: Real Shell Actions
The composer MUST append messages to history and dispatch generation on submit. The shell MUST open a file picker on "Upload Asset" click and store the selected file as a Data URI.

##### Scenario: Real send and upload
- GIVEN a valid prompt and "Upload Asset" clicked
- WHEN Enter is pressed and a valid image is selected
- THEN the message appends, generation dispatches, and the Data URI is stored

### MODIFIED Requirements

#### Requirement: Status Announcement
The canvas status text SHALL live in an element with `aria-live="polite"` and SHALL derive from the active generation job, reading idle when no job is active.
(Previously: status text was static/facade-only.)

##### Scenario: Idle status announced
- GIVEN `currentJob` is null
- WHEN the canvas renders
- THEN the status element contains the idle text

##### Scenario: Status changes are announced
- GIVEN the status reads "GENERATING..."
- WHEN the text changes to "COMPLETED in 12.4s"
- THEN screen readers announce the new text without stealing focus

### REMOVED Requirements

#### Requirement: Facade-Only Behavior
(Reason: View3 is wired to real generation state; the shell no longer uses mock data or no-op actions.)
(Migration: Replace no-op tests with tests for real submission and upload.)
