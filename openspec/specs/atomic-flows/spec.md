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

The system MUST define `ImageArtifact` with `volume_path`, `media_type`, `source_job_id`, `width`, and `height`. It SHALL accept `volume_path`, `url`, or `upload` sources, but `volume_path` MUST be the primary handoff path between flows. The system MUST validate that `volume_path` stays within the job volume root and that `media_type` is `image/png` or `image/jpeg`.

#### Scenario: Prior flow output feeds next flow

- GIVEN a composition request referencing an extraction output artifact by `volume_path`
- WHEN the composition flow executes
- THEN it reads the PNG from the validated volume path

#### Scenario: Artifact path escape rejected

- GIVEN an artifact with `volume_path = "../../../etc/passwd"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Unsupported media type rejected

- GIVEN an artifact with `media_type = "image/webp"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_media_type"`

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
