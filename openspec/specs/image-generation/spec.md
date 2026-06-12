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
