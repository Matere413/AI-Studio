# Delta for Image Generation

## MODIFIED Requirements

### Requirement: Accept Generation Requests

The system MUST expose `POST /generate` and accept `application/json` with required `prompt` plus optional workflow-selection parameters. Only three workflows are supported: `flux2_txt2img`, `flux2_editing`, and `identidad_gguf`. Any other `workflow` value MUST be rejected with HTTP 400 and `error.code = "unsupported_workflow"`. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.
(Previously: Accepted any declared workflow including `qwen_txt2img`, `realistic_persona`, `product_premium`, `txt2img`, `controlnet`, `img2img`.)

#### Scenario: Dynamic generation request accepted

- GIVEN a client sends a valid prompt and a supported workflow (`flux2_txt2img`, `flux2_editing`, or `identidad_gguf`)
- WHEN `POST /generate` is called
- THEN the request is accepted for the selected generation workflow

#### Scenario: Unsupported generation parameter rejected

- GIVEN a client sends a parameter not declared by the selected workflow
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Legacy workflow rejected

- GIVEN a client sends `workflow = "qwen_txt2img"` or `workflow = "realistic_persona"` or `workflow = "product_premium"`
- WHEN `POST /generate` is called
- THEN the request is rejected with HTTP 400 and `error.code = "unsupported_workflow"`

### Requirement: Stream Job Lifecycle

The system MUST expose `WS /ws/generate/{job_id}` sending JSON messages with `required: [event, job_id, timestamp]`, `additionalProperties: false`. Event enum: `["booting_server", "downloading_weights", "generating", "progress", "completed", "error"]`. `progress` field: integer 0–100. `completed` MUST include `result.image_path`. `error` MUST include `error.code` and `error.detail`. Required error codes: `"timeout"`, `"model_not_allowed"`, `"comfyui_execution_failed"`, `"job_not_found"`.

#### Scenario: Lifecycle streamed to completion

- GIVEN a valid `job_id` exists
- WHEN a client connects to `WS /ws/generate/{job_id}`
- THEN the server sends granular events as the job advances
- AND the final event is `completed` with `result.image_path`

#### Scenario: Client reconnects

- GIVEN a job is still active and a client disconnects
- WHEN the client reconnects with the same `job_id`
- THEN the server resumes by sending the current known lifecycle state

#### Scenario: Timeout error event

- GIVEN a job exceeds the 300-second timeout
- WHEN the timeout is triggered
- THEN the server sends a terminal `error` event with `error.code = "timeout"`

### Requirement: Report Invalid or Failed Jobs

The system SHALL terminate the WebSocket stream with a single terminal event. Unknown jobs MUST produce `error` with a not-found code. Failed executions MUST produce `error` with a failure code. After `completed` or `error`, no further lifecycle events MUST be sent for that connection.

#### Scenario: Unknown job

- GIVEN no job exists for the requested `job_id`
- WHEN a client connects to `WS /ws/generate/{job_id}`
- THEN the server sends an `error` event with a not-found code

#### Scenario: Job execution fails

- GIVEN a generation job starts but cannot complete
- WHEN the failure is detected
- THEN the server sends a terminal `error` event with failure details

### Requirement: Serve Generated Images via HTTP

The system MUST expose `GET /images/{job_id}` returning the generated image for a completed job. Responses: `200` with `Content-Type: image/png` or `image/jpeg` when the image exists; `404` with `error.code = "image_not_found"` when the job exists but produced no image; `404` with `error.code = "job_not_found"` when the job_id does not exist.

#### Scenario: Image served for completed job

- GIVEN a job completed with an image in the Modal Volume
- WHEN a client calls `GET /images/{job_id}`
- THEN the server returns `200` with the image binary and correct `Content-Type`

#### Scenario: No image produced

- GIVEN a job completed but produced no image file
- WHEN a client calls `GET /images/{job_id}`
- THEN the server returns `404` with `error.code = "image_not_found"`

#### Scenario: Job not found

- GIVEN no job exists for the requested job_id
- WHEN a client calls `GET /images/{job_id}`
- THEN the server returns `404` with `error.code = "job_not_found"`

### Requirement: Enforce Hard Timeout on Generation

The system MUST enforce a 300-second hard timeout on the full generation pipeline (ComfyUI boot + execution + output retrieval). On timeout, the system MUST terminate the process, set job state to `error` with `error.code = "timeout"`, and emit a terminal `error` WebSocket event.

#### Scenario: Generation completes within timeout

- GIVEN a valid generation request is submitted
- WHEN ComfyUI completes within 300 seconds
- THEN the job transitions to `completed` normally

#### Scenario: Generation exceeds timeout

- GIVEN a valid generation request is submitted
- WHEN the pipeline exceeds 300 seconds
- THEN the process is terminated and the job receives `error` with `code = "timeout"`

### Requirement: Emit Granular WebSocket Progress States

The system MUST extend the WebSocket `event` enum to: `["booting_server", "downloading_weights", "generating", "progress", "completed", "error"]`. `generating` and `progress` events MUST include numeric `progress` (0–100). All events MUST include `job_id` and `timestamp`.

#### Scenario: Granular progress during generation

- GIVEN a job is executing on ComfyUI
- WHEN generation progresses through stages
- THEN the server emits `booting_server`, `downloading_weights`, `generating` with numeric `progress`

#### Scenario: Progress value bounded

- GIVEN a job is emitting progress events
- WHEN any `progress` event is sent
- THEN `progress` is an integer between 0 and 100 inclusive

## REMOVED Requirements

### Requirement: Accept Product Workflow Requests

(Reason: `product_premium` workflow is retired as part of the Flux 2 refactor.)
(Migration: Clients should use `flux2_txt2img` with appropriate prompts.)

### Requirement: Accept Realistic Persona Workflow Requests

(Reason: `realistic_persona` workflow is retired as part of the Flux 2 refactor.)
(Migration: Clients should use `flux2_editing` with identity reference images.)

### Requirement: Optional Image Fallback Behavior

(Reason: Tied to `realistic_persona` FaceID conditioning which is retired.)
(Migration: Flux 2 editing uses required `image_base64` with no fallback.)

### Requirement: Accept Qwen Text-to-Image Workflow Requests

(Reason: `qwen_txt2img` workflow is retired as part of the Flux 2 refactor.)
(Migration: Clients should use `flux2_txt2img` with `use_turbo` toggle.)
