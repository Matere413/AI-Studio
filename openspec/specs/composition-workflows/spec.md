# Composition Workflows Specification

## Purpose

Define the contract for FLUX + ControlNet composition workflows. Combines a foreground subject with a generated or controlled background using depth or canny edge guidance.

## Requirements

### Requirement: Composition inputs

The composition flow MUST accept `prompt`, `background_image: ImageArtifact`, `foreground_image: ImageArtifact`, `control_mode ∈ {"depth", "canny"}`, optional `control_strength` (0.0–2.0, default 1.0), and optional `seed`.

#### Scenario: Extraction output feeds composition

- GIVEN a valid transparent PNG artifact from the extraction flow
- WHEN composition runs with `control_mode = "depth"`
- THEN the foreground subject is composed onto a generated background matching depth guidance

#### Scenario: Explicit upload feeds composition

- GIVEN a user-uploaded foreground and background image
- WHEN composition runs with `control_mode = "canny"`
- THEN the output respects the uploaded foreground and canny edge guidance

#### Scenario: Invalid control_mode rejected

- GIVEN `control_mode = "pose"`
- WHEN validated
- THEN the request is rejected

### Requirement: Composition pipeline

The system MUST execute a FLUX + ControlNet graph: preprocess the background, apply ControlNet conditioning, encode the foreground via VAE, sample with FLUX UNet, decode, and save. The flow SHALL run on `gpu_profile = L4` or higher with `timeout_s = 600`.

#### Scenario: Depth mode produces coherent scene

- GIVEN valid background, foreground, and `control_mode = "depth"`
- WHEN the workflow runs
- THEN the generated image places the foreground at a depth consistent with the background

#### Scenario: ControlNet model missing fails fast

- GIVEN the requested ControlNet model is not cached
- WHEN the flow spawns
- THEN it fails with `error.code = "model_not_cached"`

#### Scenario: VRAM pressure handled

- GIVEN the L4 profile exhausts VRAM during sampling
- WHEN the error is caught
- THEN the system returns `error.code = "gpu_oom"` and retries are not attempted automatically

### Requirement: Composition outputs

The flow MUST return a composed image `ImageArtifact` with `media_type = "image/png"` and dimensions matching the requested or default resolution.
