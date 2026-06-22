# Observability Specification

## Purpose

Provide production-grade observability for the image-generation pipeline through structured logs and optional Sentry error reporting, without requiring Sentry in development.

## Requirements

### Requirement: Structured Request Logging

The system MUST emit one structured log line per HTTP request containing at least `method`, `path`, `status_code`, `duration_ms`, and `correlation_id`.

#### Scenario: Successful generation request

- GIVEN `POST /generate` returns `202 Accepted`
- WHEN the response completes
- THEN a request log with `status_code=202` and `duration_ms` is emitted

#### Scenario: Failed request

- GIVEN `POST /generate` raises a validation error
- WHEN the response completes
- THEN a request log with `status_code=422` and the same `correlation_id` is emitted

### Requirement: Structured Job Lifecycle Logs

The system MUST emit structured logs for job state transitions: `created`, `booting_server`, `downloading_weights`, `generating`, `completed`, `error`.

#### Scenario: Job completes

- GIVEN a generation job reaches `completed`
- WHEN the terminal event is emitted
- THEN a job log with `event=completed`, `job_id`, and `duration_ms` is emitted

#### Scenario: Job fails

- GIVEN a job fails with `comfyui_execution_failed`
- WHEN the failure is recorded
- THEN a job log with `event=error`, `job_id`, and `error.code` is emitted

### Requirement: Optional Sentry Initialization

The system MUST initialize Sentry only when `SENTRY_DSN` is set; otherwise Sentry MUST remain disabled with no external network calls.

#### Scenario: Sentry enabled

- GIVEN `SENTRY_DSN` is configured
- WHEN the application starts
- THEN Sentry SDK is initialized with the FastAPI integration

#### Scenario: Sentry disabled

- GIVEN `SENTRY_DSN` is unset
- WHEN the application starts
- THEN Sentry is not initialized and structured logging continues normally

### Requirement: Sentry Capture for Critical Failure Modes

The system MUST capture the following failures to Sentry when enabled: GPU OOM, missing ComfyUI node, generation timeout, and any uncaught FastAPI exception.

#### Scenario: GPU OOM

- GIVEN a Modal GPU function exits with an OOM error
- WHEN the error is handled
- THEN the exception is sent to Sentry with `error_type=gpu_oom` and `job_id`

#### Scenario: Missing ComfyUI node

- GIVEN generation fails because a required node is missing
- WHEN the error is handled
- THEN the exception is sent to Sentry with `error_type=missing_node` and `job_id`

#### Scenario: Timeout

- GIVEN a job exceeds the 300-second timeout
- WHEN the timeout handler fires
- THEN the exception is sent to Sentry with `error_type=timeout` and `job_id`

#### Scenario: Uncaught FastAPI exception

- GIVEN an unhandled exception escapes a router
- WHEN the global exception handler receives it
- THEN the exception is sent to Sentry with request context
