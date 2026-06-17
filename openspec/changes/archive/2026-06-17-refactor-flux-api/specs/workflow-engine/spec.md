# Delta for Workflow Engine

## ADDED Requirements

### Requirement: Load Flux 2 Text-to-Image Workflow Manifest

The system MUST load the `flux2_txt2img` workflow template and manifest from `api/src/workflows/flux2_txt2img/`. The manifest MUST declare `prompt` (required, non-empty string), `seed` (optional integer, -1 for random), and `use_turbo` (optional boolean, default `true`) as supported parameters. The engine MUST validate that the manifest's referenced Flux 2 models are in the approved whitelist before loading.

#### Scenario: Flux 2 txt2img workflow loads

- GIVEN the `flux2_txt2img` directory contains a valid template and manifest
- WHEN the workflow engine loads the workflow
- THEN the engine returns a parameterizable definition with all declared parameters

#### Scenario: Flux 2 txt2img manifest references non-whitelisted model

- GIVEN the manifest references a Flux 2 model not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Load Flux 2 Editing Workflow Manifest

The system MUST load the `flux2_editing` workflow template and manifest from `api/src/workflows/flux2_editing/`. The manifest MUST declare `prompt` (required, non-empty string), `seed` (optional integer, -1 for random), `image_base64` (required, valid base64 string), and `use_turbo` (optional boolean, default `true`) as supported parameters. The manifest MUST NOT declare `width` or `height`. The engine MUST validate that the manifest's referenced Flux 2 models are in the approved whitelist before loading.

#### Scenario: Flux 2 editing workflow loads

- GIVEN the `flux2_editing` directory contains a valid template and manifest
- WHEN the workflow engine loads the workflow
- THEN the engine returns a parameterizable definition with `image_base64` mapped to `LoadImageFromBase64`

#### Scenario: Flux 2 editing manifest declares width/height

- GIVEN the `flux2_editing` manifest includes `width` or `height` parameters
- WHEN the workflow engine validates the manifest
- THEN the engine rejects with a validation error

## MODIFIED Requirements

### Requirement: Execute Parameterized Workflows

The system MUST apply runtime parameters through the manifest and execute the resolved workflow. The system SHALL support `flux2_txt2img`, `flux2_editing`, and `identidad_gguf` workflows through the same execution contract.
(Previously: Supported text-to-image, image-to-image, ControlNet, product_premium, realistic_persona, and qwen_txt2img workflows.)

#### Scenario: Execute Flux 2 text-to-image workflow

- GIVEN a `flux2_txt2img` template and valid prompt parameters
- WHEN the engine executes the workflow
- THEN ComfyUI receives a resolved graph with turbo toggle applied

#### Scenario: Execute Flux 2 editing workflow

- GIVEN a `flux2_editing` template and required `image_base64` input
- WHEN the engine executes the workflow
- THEN the resolved graph includes the base64-decoded image via `LoadImageFromBase64`

#### Scenario: Execute identity GGUF workflow

- GIVEN an `identidad_gguf` template and required `image_url` input
- WHEN the engine executes the workflow
- THEN the resolved graph includes the downloaded reference image

## REMOVED Requirements

### Requirement: Load Product Premium Workflow Manifest

(Reason: `product_premium` workflow is retired.)
(Migration: Use `flux2_txt2img` for product imagery.)

### Requirement: Resolve Product-Specific Parameters

(Reason: `product_premium` format resolution is retired with the workflow.)
(Migration: None.)

### Requirement: Load Realistic Persona Workflow Manifest

(Reason: `realistic_persona` workflow is retired.)
(Migration: Use `flux2_editing` with identity reference images.)

### Requirement: Resolve Persona-Specific Parameters

(Reason: Persona control resolution is retired with the workflow.)
(Migration: None.)

### Requirement: Load Qwen Text-to-Image Workflow Manifest

(Reason: `qwen_txt2img` workflow is retired.)
(Migration: Use `flux2_txt2img` with `use_turbo` toggle.)

### Requirement: Resolve Qwen Dimensions and Quality Mode

(Reason: Qwen quality mode resolution is retired with the workflow.)
(Migration: Use `use_turbo` boolean instead of `quality_mode` enum.)
