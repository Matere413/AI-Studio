# Image Generation Specification

## Purpose

Define the MVP contract for creating an image-generation job over HTTP and observing its lifecycle over WebSocket. The system uses Modal distributed infrastructure: the API runs on CPU while generation executes on GPU via Modal background functions, and job state is persisted across containers using `modal.Dict` distributed storage.

## Requirements

### Requirement: Accept Generation Requests

The system MUST expose `POST /generate` and accept `application/json` with required `prompt` plus optional workflow-selection parameters for `checkpoint`, `lora`, and other declared generation inputs. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

(Previously: `POST /generate` accepted only a prompt for one hardcoded txt2img workflow.)

#### Scenario: Dynamic generation request accepted

- GIVEN a client sends a valid prompt and supported generation parameters
- WHEN `POST /generate` is called
- THEN the request is accepted for the selected generation workflow

#### Scenario: Unsupported generation parameter rejected

- GIVEN a client sends a parameter not declared by the selected workflow
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

### Requirement: Stream Job Lifecycle

The system MUST expose `WS /ws/generate/{job_id}` sending JSON messages with `required: [event, job_id, timestamp]`, `additionalProperties: false`. Event enum: `["booting_server", "downloading_weights", "generating", "progress", "completed", "error"]`. `progress` field: integer 0–100. `completed` MUST include `result.image_path`. `error` MUST include `error.code` and `error.detail`. Required error codes: `"timeout"`, `"model_not_allowed"`, `"comfyui_execution_failed"`, `"job_not_found"`.
(Previously: event enum was `["pending", "running", "completed", "error"]` with no granular states or specific error codes.)

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

### Requirement: Accept Product Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "product_premium"` and a free-form `prompt`. When `workflow = "product_premium"`, the request MAY include an optional `format` field with values `"square"` or `"vertical"` (default: `"square"`). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Product workflow request accepted

- GIVEN a client sends `prompt` and `workflow = "product_premium"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Product workflow with vertical format

- GIVEN a client sends `prompt`, `workflow = "product_premium"`, and `format = "vertical"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and the vertical format is recorded

#### Scenario: Product workflow with invalid format rejected

- GIVEN a client sends `workflow = "product_premium"` and `format = "panoramic"`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

### Requirement: Accept Realistic Persona Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "realistic_persona"` and declared persona controls: `age` (integer, 18-100), `gender` (non-empty string), `ethnicity` (non-empty string), `wardrobe` (non-empty string), `expression` (non-empty string), and `background` (non-empty string). The request MAY include an optional `image_url` field containing a URL to a reference face image for identity preservation. When `image_url` is present, the system MUST apply FaceID conditioning. When `image_url` is absent, the system MUST fall back to prompt-only generation. The system MUST reject requests with undeclared controls, empty string values, or values outside declared ranges. Omitted optional persona controls MUST fall back to workflow manifest defaults. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

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

### Requirement: Accept Qwen Text-to-Image Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "qwen_txt2img"` and parameters: `prompt` (required, non-empty string), `negative_prompt` (optional string), `width` (optional integer, default from manifest), `height` (optional integer, default from manifest), and `quality_mode` (optional enum: `["fast", "high"]`, default `"high"`). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Qwen workflow request accepted

- GIVEN a client sends `workflow = "qwen_txt2img"` with a valid `prompt`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Qwen workflow with custom dimensions and quality mode

- GIVEN a client sends `workflow = "qwen_txt2img"` with `width = 768`, `height = 1024`, `quality_mode = "fast"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and all parameters are recorded

#### Scenario: Qwen workflow with invalid workflow parameter rejected

- GIVEN a client sends `workflow = "qwen_txt2img"` with an undeclared parameter `seed_strategy`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

## Architecture Decisions

### State Persistence: modal.Dict Distributed Store

Job lifecycle state is persisted using `modal.Dict` — a distributed key-value store provided by Modal that survives individual container restarts and is accessible from both the API (CPU) and background GPU function containers. This replaces the originally proposed in-memory dict, enabling:

- **Cross-container visibility**: The API container writes job state; the GPU function reads/writes the same state; the WebSocket handler polls from the same store.
- **Resilience to container restarts**: If the API container is recycled, in-flight jobs persist in the distributed store and remain observable via WebSocket.
- **No external infrastructure**: `modal.Dict` requires no Redis, database, or external broker — it is part of Modal's managed infrastructure.

The API layer accesses the store synchronously for single-shot lookups and asynchronously (`get_job_async`) during the WebSocket polling loop to avoid Modal blocking-interface warnings.

### Architecture Overview

```
┌──────────┐     POST /generate      ┌──────────────────────┐
│          │ ──────────────────────►  │  FastAPI Router      │
│  Client  │                          │  (CPU Container)     │
│          │ ◄── 202 Accepted ──────  │                      │
│          │                          │  JobStore            │
│          │     WS /ws/generate      │  (modal.Dict)        │
│          │ ──────────────────────►  │                      │
│          │ ◄─── lifecycle events ── │                      │
└──────────┘                          └───────┬──────────────┘
                                              │ .spawn()
                                              ▼
                                     ┌──────────────────────┐
                                     │  run_generation      │
                                     │  (GPU Function)      │
                                     │                      │
                                     │  JobStore            │
                                     │  (modal.Dict)        │
                                     └──────────────────────┘
```
