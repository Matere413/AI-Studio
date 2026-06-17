# Delta for generative-ai-studio-frontend

## ADDED Requirements

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

### Requirement: Lateral Identity Settings Panel

The system MUST compose a lateral identity panel within `GenerationStudio` containing: gallery selector, custom upload button, image preview, and workflow warning text. The panel MUST use existing Matere Design System primitives.

#### Scenario: Panel renders active

- GIVEN `identidad_gguf` is active
- WHEN the panel renders
- THEN gallery selector, upload button, and empty preview are visible

#### Scenario: Panel disabled for non-applicable workflow

- GIVEN a non-identity workflow is active with a stored reference image
- WHEN the panel renders
- THEN the preview is grayed with "Not applicable for this workflow" and the image is NOT cleared

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
