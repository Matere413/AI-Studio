# Atomic Flows Specification

## Purpose

Define the typed flow contract for composable atomic flow modules. Each atomic flow owns its Pydantic v2 request model, GPU profile, and image-input strategy — decoupling from the monolithic `GenerateRequest` and enabling artifact-based chaining between flows.

## Requirements

### Requirement: BaseAtomicFlow typed contract

The system MUST define `BaseAtomicFlow` as a Pydantic v2 base model with fields `workflow_name`, `gpu_profile`, `timeout_s`, and `prompt`. Each concrete flow SHALL subclass it, bind a unique `workflow_name`, and register in the flow registry.

#### Scenario: Valid flow subclass registers

- GIVEN an `ExtractionFlow` subclass declaring `workflow_name = "extraction"`
- WHEN the flow registry loads
- THEN the flow is exposed under `"extraction"`

#### Scenario: Missing workflow_name rejected

- GIVEN a subclass omits `workflow_name`
- WHEN the model is validated
- THEN Pydantic raises a validation error

#### Scenario: Prompt length enforced

- GIVEN a request with `prompt` longer than 4000 characters
- WHEN validated
- THEN the request is rejected

### Requirement: ImageArtifact handoff

The system MUST define `ImageArtifact` with `volume_path`, `media_type`, `source_job_id`, `width`, `height`, and `asset_id` (optional). It SHALL accept `volume_path`, `url`, `asset_id`, or `upload` sources, but `volume_path` MUST be the primary handoff path between flows. The system MUST validate that `volume_path` stays within the job volume root. Validated media types MUST include `image/png`, `image/jpeg`, and `image/webp`. For `volume_path` under `input/`, the path MUST contain a Session UUID segment matching the request session; otherwise the artifact MUST be rejected. When an `asset_id` is provided, the system MUST resolve it to a fresh presigned GET URL for the `LoadImageFromUrl` node.
(Previously: `input/` uploads were accepted without session ownership validation, `asset_id` did not exist, and `image/webp` was rejected.)

#### Scenario: Prior flow output feeds next flow

- GIVEN a composition request referencing an extraction output artifact by `volume_path`
- WHEN the composition flow executes
- THEN it reads the PNG from the validated volume path

#### Scenario: Artifact path escape rejected

- GIVEN an artifact with `volume_path = "../../../etc/passwd"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: WebP media type accepted

- GIVEN an artifact with `media_type = "image/webp"`
- WHEN validated
- THEN the artifact is accepted

#### Scenario: Valid session-owned input accepted

- GIVEN an artifact with `volume_path = "input/{session_uuid}/face.png"` and matching session
- WHEN validated
- THEN the artifact is accepted

#### Scenario: Input path with mismatched session rejected

- GIVEN an artifact with `volume_path = "input/{other_session_uuid}/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Input path without session segment rejected

- GIVEN an artifact with `volume_path = "input/face.png"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Generated artifact handoff ignores session check

- GIVEN a generated artifact with `volume_path = "output/{job_id}/image.png"` and `source_job_id`
- WHEN validated in any session
- THEN the artifact is accepted

#### Scenario: Asset_id resolves to URL

- GIVEN an `ImageArtifact` with a valid owned `asset_id`
- WHEN the flow executes
- THEN `LoadImageFromUrl` receives a fresh presigned GET URL

### Requirement: FlowOutput contract

The system MUST return `FlowOutput` containing `job_id` and `artifacts: list[ImageArtifact]`. Every successful flow execution MUST emit at least one artifact.

#### Scenario: Successful flow returns artifacts

- GIVEN a flow completes without errors
- WHEN the response is built
- THEN `FlowOutput.artifacts` contains one or more valid `ImageArtifact` entries

### Requirement: Typed flow dispatch

The system MUST route requests through per-flow Pydantic v2 models and MUST NOT extend the monolithic `GenerateRequest` for new atomic flows.

#### Scenario: Typed request accepted

- GIVEN `POST /generate/extraction` with a valid `ExtractionRequest`
- WHEN validated
- THEN the job is accepted and routed to the extraction flow

#### Scenario: Monolithic field rejected

- GIVEN a typed flow request contains a field from `GenerateRequest` not in its schema
- WHEN validated
- THEN the request is rejected with a validation error
