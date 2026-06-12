# Image Generation Specification

## Purpose

Define the MVP contract for creating an image-generation job over HTTP and observing its lifecycle over WebSocket.

## Requirements

### Requirement: Accept Generation Requests

The system MUST expose `POST /generate` and accept `application/json` with this schema: `type: object`, `required: [prompt]`, `additionalProperties: false`, `properties: { prompt: { type: string, minLength: 1, maxLength: 4000 } }`. The system MUST return `202 Accepted` with schema: `type: object`, `required: [job_id, status]`, `additionalProperties: false`, `properties: { job_id: { type: string, minLength: 1 }, status: { const: "pending" } }`.

#### Scenario: Request accepted

- GIVEN a client sends a valid non-empty `prompt`
- WHEN `POST /generate` is called
- THEN the response status is `202`
- AND the body contains a unique `job_id` and `status = "pending"`

#### Scenario: Request rejected

- GIVEN a client omits `prompt` or sends an empty string
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

### Requirement: Stream Job Lifecycle

The system MUST expose `WS /ws/generate/{job_id}`. After connection, the server MUST send JSON messages with schema: `type: object`, `required: [event, job_id, timestamp]`, `additionalProperties: false`, `properties: { event: { enum: ["pending", "running", "completed", "error"] }, job_id: { type: string }, timestamp: { type: string, format: "date-time" }, progress: { type: integer, minimum: 0, maximum: 100 }, message: { type: string }, result: { type: object, additionalProperties: false, properties: { image_path: { type: string, minLength: 1 } } }, error: { type: object, additionalProperties: false, properties: { code: { type: string }, detail: { type: string } } } }`. `pending` and `running` MAY include `progress` and `message`. `completed` MUST include `result.image_path`. `error` MUST include `error.code` and `error.detail`.

#### Scenario: Lifecycle streamed to completion

- GIVEN a valid `job_id` exists
- WHEN a client connects to `WS /ws/generate/{job_id}`
- THEN the server sends `pending` and `running` events as the job advances
- AND the final event is `completed` with `result.image_path`

#### Scenario: Client reconnects

- GIVEN a job is still active and a client disconnects
- WHEN the client reconnects with the same `job_id`
- THEN the server resumes by sending the current known lifecycle state

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
