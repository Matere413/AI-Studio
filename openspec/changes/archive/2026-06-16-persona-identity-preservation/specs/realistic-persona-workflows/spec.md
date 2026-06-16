# Delta for Realistic Persona Workflows

## MODIFIED Requirements

### Requirement: Default Checkpoint and Aesthetic Boundaries

The system MUST use `RealVisXL_V4.0.safetensors` as the default checkpoint for `realistic_persona`. The checkpoint identifier MUST be configurable for future validation. When a reference face image is provided, the system MUST apply IP-Adapter FaceID Plus V2 SDXL conditioning. When no reference face image is provided, the system MUST fall back to prompt-only generation using the text prompt and persona controls. The workflow MUST NOT include FaceDetailer, InstantID, or multi-face identity preservation.
(Previously: Used `juggernautXL_ragnarok.safetensors` and explicitly excluded all identity preservation including IPAdapter.)

#### Scenario: Default checkpoint applied

- GIVEN a `realistic_persona` request without explicit checkpoint override
- WHEN the workflow executes
- THEN `RealVisXL_V4.0.safetensors` is used as the generation checkpoint

#### Scenario: Identity preservation with reference face

- GIVEN a `realistic_persona` request with a valid reference face image URL
- WHEN the workflow executes
- THEN IP-Adapter FaceID Plus V2 SDXL conditioning is applied to the generation

#### Scenario: Prompt-only fallback without reference face

- GIVEN a `realistic_persona` request with no reference face image
- WHEN the workflow executes
- THEN generation proceeds using prompt + persona controls only, no IP-Adapter nodes

## ADDED Requirements

### Requirement: Optional FaceID Conditioning

The system MUST support optional IP-Adapter FaceID Plus V2 SDXL identity conditioning from a single reference face image. The reference image MUST be provided as a URL. When the reference image is present, the system MUST apply FaceID conditioning at the SDXL level. The system MUST NOT attempt multi-face identity, InstantID, or PuLID conditioning.

#### Scenario: FaceID conditioning applied

- GIVEN a valid reference face image URL is provided
- WHEN the `realistic_persona` workflow executes
- THEN the IP-Adapter FaceID Plus V2 SDXL node receives the reference image and applies identity conditioning

#### Scenario: Invalid reference image URL rejected

- GIVEN a reference face image URL that is unreachable or not a valid image
- WHEN the workflow validates the reference
- THEN the workflow falls back to prompt-only generation and logs a warning

#### Scenario: FaceID strength is configurable

- GIVEN a `realistic_persona` request with FaceID conditioning
- WHEN the workflow executes
- THEN the FaceID strength defaults to a value that preserves likeness without overfitting

### Requirement: Reference Face Image Validation

The system MUST validate that a provided reference face image URL is accessible and contains a detectable face before applying FaceID conditioning. If face detection fails, the system MUST fall back to prompt-only generation and MUST NOT fail the entire request.

#### Scenario: Face detected in reference

- GIVEN a reference image URL with a clearly visible face
- WHEN the system validates the reference
- THEN face detection succeeds and FaceID conditioning proceeds

#### Scenario: No face detected in reference

- GIVEN a reference image URL with no detectable face (e.g., landscape, object)
- WHEN the system validates the reference
- THEN the system falls back to prompt-only generation without error to the user

#### Scenario: Reference image unreachable

- GIVEN a reference image URL that returns 404 or times out
- WHEN the system validates the reference
- THEN the system falls back to prompt-only generation without error to the user
