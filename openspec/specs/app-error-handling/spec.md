# App Error Handling Specification

## Purpose

Centralize HTTP error handling and sanitize internal implementation details from public error responses.

## Requirements

### Requirement: Centralized Exception Handler

The system MUST register a single FastAPI exception handler that maps application exceptions to HTTP responses. Router code MUST NOT duplicate 422/500 mapping logic.

#### Scenario: Validation error from handler

- GIVEN a Pydantic validation error is raised
- WHEN the central handler processes it
- THEN it returns HTTP 422 with FastAPI-compatible `detail`

#### Scenario: Operational error from handler

- GIVEN an `AppException` with `code` and `detail` is raised
- WHEN the central handler processes it
- THEN it returns the configured HTTP status and `{ error: { code, detail } }`

#### Scenario: Router without duplicated try/except

- GIVEN `GET /images/{job_id}` is implemented
- WHEN the source is inspected
- THEN no inline 422/500 mapping try/except blocks are present

### Requirement: Sanitized Public Error Details

The system MUST NOT expose raw ComfyUI `node_id`, absolute file paths, internal ComfyUI directory names, Modal Volume paths, or exception tracebacks in public error responses.

#### Scenario: ComfyUI execution failure

- GIVEN ComfyUI returns an error containing a raw `node_id` and path
- WHEN the public `error` WebSocket event or HTTP response is built
- THEN the `detail` contains a generic message and the internal identifiers are removed

#### Scenario: Image not found

- GIVEN `GET /images/{job_id}` returns `404`
- WHEN the response body is built
- THEN the body contains `error.code = "image_not_found"` and no file-system path

#### Scenario: Internal server error

- GIVEN an unexpected exception occurs
- WHEN the public response is built
- THEN the body contains `error.code = "internal_error"` and `detail` is generic
- AND the full traceback is only in structured logs

### Requirement: Preserved Error Code Contracts

The system MUST keep the existing public error codes: `timeout`, `model_not_allowed`, `comfyui_execution_failed`, `job_not_found`, `image_not_found`, `unsupported_workflow`, `invalid_artifact`, `invalid_media_type`.

#### Scenario: Timeout event

- GIVEN a job times out
- WHEN the terminal event is emitted
- THEN `error.code` remains `"timeout"`

#### Scenario: Unsupported workflow

- GIVEN `POST /generate` receives a legacy workflow
- WHEN the request is rejected
- THEN `error.code` remains `"unsupported_workflow"`
