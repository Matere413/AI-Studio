# Delta for Image Generation

## MODIFIED Requirements

### Requirement: Stream Job Lifecycle

The system MUST expose `WS /ws/generate/{job_id}` sending JSON messages with `required: [event, job_id, timestamp]`, `additionalProperties: false`. Event enum: `["booting_server", "downloading_weights", "generating", "progress", "completed", "error"]`. `progress` field: integer 0–100. `completed` MUST include `result.image_url` derived from `job_id`. `error` MUST include `error.code` and a sanitized `error.detail` containing no raw `node_id`, absolute path, or internal ComfyUI path. Required error codes: `"timeout"`, `"model_not_allowed"`, `"comfyui_execution_failed"`, `"job_not_found"`.
(Previously: `completed` included `result.image_path`; `error.detail` could contain raw node/path metadata.)

#### Scenario: Lifecycle streamed to completion

- GIVEN a valid `job_id` exists
- WHEN a client connects to `WS /ws/generate/{job_id}`
- THEN the server sends granular events as the job advances
- AND the final event is `completed` with `result.image_url = "/images/{job_id}"`

#### Scenario: Client reconnects

- GIVEN a job is still active and a client disconnects
- WHEN the client reconnects with the same `job_id`
- THEN the server resumes by sending the current known lifecycle state

#### Scenario: Timeout error event

- GIVEN a job exceeds the 300-second timeout
- WHEN the timeout is triggered
- THEN the server sends a terminal `error` event with `error.code = "timeout"` and sanitized detail

#### Scenario: Sanitized ComfyUI failure

- GIVEN ComfyUI fails with a raw `node_id` and internal path
- WHEN the `error` event is emitted
- THEN `error.detail` contains no raw `node_id` or internal path

### Requirement: Report Invalid or Failed Jobs

The system SHALL terminate the WebSocket stream with a single terminal event. Unknown jobs MUST produce `error` with a not-found code. Failed executions MUST produce `error` with a failure code and sanitized detail. After `completed` or `error`, no further lifecycle events MUST be sent for that connection.
(Previously: failure details could include internal metadata.)

#### Scenario: Unknown job

- GIVEN no job exists for the requested `job_id`
- WHEN a client connects to `WS /ws/generate/{job_id}`
- THEN the server sends an `error` event with a not-found code

#### Scenario: Job execution fails

- GIVEN a generation job starts but cannot complete
- WHEN the failure is detected
- THEN the server sends a terminal `error` event with failure code and sanitized detail

## ADDED Requirements

### Requirement: Structured Failure Reporting

The system MUST log and optionally report to Sentry all terminal failures emitted through the WebSocket stream.

#### Scenario: Failure logged

- GIVEN an `error` event is emitted
- WHEN the event is built
- THEN a structured log with `job_id`, `error.code`, and `error.detail` is emitted

#### Scenario: Sentry capture

- GIVEN Sentry is enabled and a terminal `error` event is emitted
- WHEN the event is built
- THEN the failure is captured by Sentry with `job_id`
