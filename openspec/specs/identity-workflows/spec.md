# Identity Workflows Specification

## Purpose

Define the contract for PuLID + FLUX identity-preserving generation. Replaces the legacy `identidad_gguf` workflow with a modern PuLID + FLUX approach running on A100 GPUs.

## Requirements

### Requirement: Identity inputs

The identity flow MUST accept `prompt`, `reference_face: ImageArtifact`, optional `seed`, and optional `width`/`height` that are multiples of 64.

#### Scenario: Valid identity request

- GIVEN a front-facing identity reference artifact
- WHEN the PuLID + FLUX workflow runs
- THEN the generated image preserves the subject's identity

#### Scenario: Non-face reference rejected

- GIVEN a reference image with no detectable face
- WHEN the face detector runs
- THEN the flow fails with `error.code = "no_face_detected"`

#### Scenario: Invalid resolution rejected

- GIVEN `width = 1000` (not a multiple of 64)
- WHEN validated
- THEN the request is rejected

### Requirement: Identity pipeline

The system MUST execute a PuLID + FLUX graph: `LoadImage(face) → PuLIDModelLoader → ApplyPuLID → CLIPTextEncode → KSampler(FLUX UNet) → VAEDecode → SaveImage`. The flow SHALL default to `gpu_profile = A100` with `timeout_s = 1200`, and MAY fall back to `L4` with fp8 optimization when A100 is unavailable.

#### Scenario: Identity preserved across prompts

- GIVEN the same reference face and two different prompts
- WHEN both workflows complete
- THEN the generated faces are recognizably the same person

#### Scenario: PuLID model not whitelisted

- GIVEN the PuLID model is absent from the whitelist
- WHEN the request is validated
- THEN it is rejected with `error.code = "model_not_allowed"`

#### Scenario: Missing PuLID node fails fast

- GIVEN the `ComfyUI-PuLID-Flux` node is not installed
- WHEN the flow spawns
- THEN it fails with `error.code = "node_missing"`

### Requirement: Identity output

The flow MUST return a generated image `ImageArtifact` with `media_type = "image/png"` and dimensions that are multiples of 64.
