# Delta for Image Generation

## MODIFIED Requirements

### Requirement: Accept Realistic Persona Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "realistic_persona"` and declared persona controls: `age` (integer, 18-100), `gender` (non-empty string), `ethnicity` (non-empty string), `wardrobe` (non-empty string), `expression` (non-empty string), and `background` (non-empty string). The request MAY include an optional `image_url` field containing a URL to a reference face image for identity preservation. When `image_url` is present, the system MUST apply FaceID conditioning. When `image_url` is absent, the system MUST fall back to prompt-only generation. The system MUST reject requests with undeclared controls, empty string values, or values outside declared ranges. Omitted optional persona controls MUST fall back to workflow manifest defaults. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.
(Previously: Did not accept `image_url`; prompt-only generation was the only mode.)

#### Scenario: Persona workflow request accepted

- GIVEN a client sends `workflow = "realistic_persona"` with valid persona controls
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Persona workflow with reference face image

- GIVEN a client sends `workflow = "realistic_persona"` with valid controls and `image_url`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and the `image_url` is forwarded for FaceID conditioning

#### Scenario: Persona workflow without reference face uses prompt-only

- GIVEN a client sends `workflow = "realistic_persona"` with valid controls but no `image_url`
- WHEN `POST /generate` is called
- THEN the request is accepted and generation proceeds with prompt + controls only

#### Scenario: Undeclared control rejected

- GIVEN a client sends `workflow = "realistic_persona"` with an undeclared control `hair_color`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Age out of range rejected

- GIVEN a client sends `age = 5` for `realistic_persona`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error for age range

#### Scenario: Invalid image_url format rejected

- GIVEN a client sends `image_url` that is not a valid URL
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error for `image_url`

## ADDED Requirements

### Requirement: Optional Image Fallback Behavior

The system MUST support optional `image_url` for workflows that accept reference images. When `image_url` is provided but the referenced image cannot be processed (unreachable, invalid format, no face detected), the system MUST silently fall back to prompt-only generation and MUST NOT return an error to the client. The fallback behavior MUST be logged for debugging purposes.

#### Scenario: Valid image_url triggers FaceID

- GIVEN a valid `image_url` pointing to an accessible image with a detectable face
- WHEN the workflow executes on Modal
- THEN FaceID conditioning is applied and generation completes normally

#### Scenario: Unreachable image_url falls back to prompt-only

- GIVEN an `image_url` that returns 404 or times out
- WHEN the workflow executes on Modal
- THEN the system logs a warning and proceeds with prompt-only generation

#### Scenario: Image without face falls back to prompt-only

- GIVEN an `image_url` pointing to an image with no detectable face
- WHEN the workflow executes on Modal
- THEN the system logs a warning and proceeds with prompt-only generation

#### Scenario: No image_url uses prompt-only

- GIVEN no `image_url` in the request
- WHEN the workflow executes on Modal
- THEN generation proceeds with prompt + persona controls only, no FaceID nodes invoked
