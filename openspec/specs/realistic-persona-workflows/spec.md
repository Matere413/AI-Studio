# Realistic Persona Workflows Specification

## Purpose

Define the contract for realistic human persona generation across portraits, full-body, lifestyle, and editorial images with controllable demographics and natural aesthetics.

## Requirements

### Requirement: Realistic Persona Generation Contract

The system MUST support a dedicated `realistic_persona` workflow that generates realistic human personas with controllable parameters: `age` (numeric range), `gender`, `ethnicity`, `wardrobe`, `expression`, and `background`. The system MUST produce natural, realistic aesthetics and MUST NOT generate plastic, waxy, or overprocessed advertising-model output.

#### Scenario: Full persona controls accepted

- GIVEN a valid `realistic_persona` request with all declared controls
- WHEN `POST /generate` is called with `workflow = "realistic_persona"`
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Natural aesthetic enforced

- GIVEN a `realistic_persona` generation completes
- WHEN the output is evaluated
- THEN the image exhibits natural skin texture and realistic proportions, not plastic or waxy

#### Scenario: Partial controls with defaults

- GIVEN a `realistic_persona` request with only `age` and `gender`
- WHEN the workflow executes
- THEN default values are applied for unspecified controls and generation proceeds

### Requirement: Output Type Support

The system MUST support profile portraits, full-body, and lifestyle/editorial output types for the `realistic_persona` workflow. The output type MUST be declared in the request and MUST influence composition and framing.

#### Scenario: Profile portrait generation

- GIVEN `output_type = "portrait"` in a `realistic_persona` request
- WHEN the workflow executes
- THEN the generated image is a head-and-shoulders composition

#### Scenario: Full-body generation

- GIVEN `output_type = "full-body"` in a `realistic_persona` request
- WHEN the workflow executes
- THEN the generated image shows the full figure with appropriate framing

### Requirement: Default Checkpoint and Aesthetic Boundaries

The system MUST use `juggernautXL_ragnarok.safetensors` as the default checkpoint for `realistic_persona`. The checkpoint identifier MUST be configurable for future validation. The workflow MUST NOT include FaceDetailer, IPAdapter, InstantID, or reference-image identity preservation in V1.

#### Scenario: Default checkpoint applied

- GIVEN a `realistic_persona` request without explicit checkpoint override
- WHEN the workflow executes
- THEN `juggernautXL_ragnarok.safetensors` is used as the generation checkpoint

#### Scenario: Identity preservation out of scope

- GIVEN a `realistic_persona` request
- WHEN the workflow is validated
- THEN no FaceDetailer, IPAdapter, or InstantID nodes are included in V1
