# Extraction/Isolation Workflows Specification

## Purpose

Define the contract for BRIA-based subject/background extraction producing transparent PNG artifacts. This flow isolates foreground subjects from their backgrounds, enabling downstream composition and editing flows.

## Requirements

### Requirement: Extraction inputs

The extraction flow MUST accept `input_image: ImageArtifact` and an optional `mask_margin`. It MUST produce a transparent PNG `ImageArtifact` declared in the manifest `outputs.artifacts`.

#### Scenario: Valid source image produces mask

- GIVEN a source image containing a foreground subject
- WHEN the BRIA extraction workflow runs
- THEN a transparent PNG is saved to the volume and returned as an artifact

#### Scenario: Missing source rejected

- GIVEN an extraction request without `input_image`
- WHEN validated
- THEN the request is rejected

#### Scenario: Invalid source media type rejected

- GIVEN `input_image.media_type = "image/webp"`
- WHEN validated
- THEN the request is rejected

### Requirement: Extraction pipeline

The system MUST execute a ComfyUI graph matching `LoadImage → BriaRMBG → SaveImage`. The output MUST be an RGBA PNG with alpha channel. The flow SHALL run on `gpu_profile = L4` or higher with `timeout_s = 300`.

#### Scenario: Complex edges handled

- GIVEN a subject with fine hair or fur against a busy background
- WHEN BRIA runs
- THEN the alpha channel preserves edge detail without background halos

#### Scenario: Missing BRIA node fails fast

- GIVEN the `ComfyUI-BRIA_AI-RMBG` node is not installed
- WHEN the flow spawns
- THEN it fails with `error.code = "node_missing"`

### Requirement: Extraction outputs

The manifest MUST declare an output artifact named `extracted_image` with `media_type = "image/png"` and `has_alpha = true`.
