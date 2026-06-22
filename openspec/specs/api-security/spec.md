# API Security Specification

## Purpose

Reduce the API attack surface by restricting CORS and binding interim uploads to the caller's session until SDD 3 S3 integration lands.

## Requirements

### Requirement: CORS Allowlist

The system MUST configure CORS with an explicit allowlist. Wildcard `*` MUST NOT be allowed. The allowlist MUST include `http://localhost` and `http://localhost:3000`, plus configured production domains.

#### Scenario: Allowed origin

- GIVEN a request originates from `http://localhost:3000`
- WHEN an API endpoint is called
- THEN the response includes the appropriate CORS headers

#### Scenario: Disallowed origin

- GIVEN a request originates from `https://evil.example.com`
- WHEN an API endpoint is called
- THEN the request is rejected with CORS error

#### Scenario: Wildcard not used

- GIVEN the CORS configuration is inspected
- THEN no entry is `*`

### Requirement: Session-Scoped Input Artifact Ownership

The system MUST reject `ImageArtifact` sources under `input/` unless the artifact is bound to the request's Session UUID.

#### Scenario: Matching session owner

- GIVEN an `ImageArtifact` with `volume_path = "input/{session_uuid}/face.png"`
- WHEN the request session UUID matches
- THEN the artifact is accepted

#### Scenario: Mismatched session owner

- GIVEN an `ImageArtifact` with `volume_path = "input/{other_session_uuid}/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Missing session segment

- GIVEN an `ImageArtifact` with `volume_path = "input/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

### Requirement: Generated Output Handoff Unchanged

The system MUST continue to allow `source_job_id`-based handoff for generated artifacts. Session ownership applies only to `input/` uploads.

#### Scenario: Generated artifact passed to next flow

- GIVEN a `FlowOutput` artifact with `source_job_id` and `volume_path` under the job output root
- WHEN the next flow consumes it
- THEN validation succeeds regardless of session
