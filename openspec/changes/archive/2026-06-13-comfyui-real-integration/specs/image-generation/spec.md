# Delta for image-generation

## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Accept Generation Requests (mock path)

(Reason: Mocked `picsum.photos` path replaced by real ComfyUI execution. Endpoint contract `POST /generate` is unchanged.)
(Migration: None — only internal implementation changes from mock to real ComfyUI.)
