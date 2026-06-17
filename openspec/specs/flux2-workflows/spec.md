# Flux 2 Workflows Specification

## Purpose

Define the contract for Flux 2 text-to-image generation and image editing workflows, including the `use_turbo` toggle and base64 image editing input.

## Requirements

### Requirement: Accept Flux 2 Text-to-Image Requests

The system MUST accept `POST /generate` requests with `workflow = "flux2_txt2img"` and parameters: `prompt` (required, non-empty string), `seed` (optional integer, -1 for random), and `use_turbo` (optional boolean, default `true`). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Flux 2 txt2img request accepted with defaults

- GIVEN a client sends `workflow = "flux2_txt2img"` with a valid `prompt`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202`, `job_id`, and `use_turbo` defaults to `true`

#### Scenario: Flux 2 txt2img with explicit turbo false

- GIVEN a client sends `workflow = "flux2_txt2img"` with `prompt` and `use_turbo = false`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and turbo mode is disabled

#### Scenario: Invalid turbo toggle rejected

- GIVEN a client sends `use_turbo` with a non-boolean value (e.g., `"yes"`, `1`)
- WHEN `POST /generate` is called
- THEN the request is rejected with HTTP 400 and `error.code = "invalid_use_turbo"`

### Requirement: Accept Flux 2 Editing Requests

The system MUST accept `POST /generate` requests with `workflow = "flux2_editing"` and parameters: `prompt` (required, non-empty string), `seed` (optional integer, -1 for random), `image_base64` (required, valid base64-encoded image string), and `use_turbo` (optional boolean, default `true`). The request MUST NOT accept `width` or `height` parameters. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Flux 2 editing request accepted

- GIVEN a client sends `workflow = "flux2_editing"` with `prompt`, `image_base64`, and `use_turbo = true`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Missing base64 image rejected

- GIVEN a client sends `workflow = "flux2_editing"` without `image_base64`
- WHEN `POST /generate` is called
- THEN the request is rejected with HTTP 400 and `error.code = "missing_image_base64"`

#### Scenario: Invalid base64 image rejected

- GIVEN a client sends `image_base64` that is not valid base64 or not a supported image format
- WHEN `POST /generate` is called
- THEN the request is rejected with HTTP 400 and `error.code = "invalid_image_base64"`

#### Scenario: Width/height parameters rejected for editing

- GIVEN a client sends `workflow = "flux2_editing"` with `width` or `height`
- WHEN `POST /generate` is called
- THEN the request is rejected with HTTP 400 and `error.code = "unsupported_parameter"`

### Requirement: Load Flux 2 Workflow Manifests

The system MUST load the `flux2_txt2img` and `flux2_editing` workflow templates and manifests from `api/src/workflows/flux2_txt2img/` and `api/src/workflows/flux2_editing/`. The manifests MUST declare their supported parameters and reference only whitelisted Flux 2 models. The `flux2_editing` manifest MUST map `image_base64` to a `LoadImageFromBase64` node target. The engine MUST validate that referenced models are in the approved whitelist before loading.

#### Scenario: Flux 2 txt2img workflow loads

- GIVEN the `flux2_txt2img` directory contains a valid template and manifest
- WHEN the workflow engine loads the workflow
- THEN the engine returns a parameterizable definition with `prompt`, `seed`, and `use_turbo`

#### Scenario: Flux 2 editing workflow loads with base64 mapping

- GIVEN the `flux2_editing` directory contains a valid template and manifest
- WHEN the workflow engine loads the workflow
- THEN the engine returns a definition mapping `image_base64` to `LoadImageFromBase64`

#### Scenario: Flux 2 manifest references non-whitelisted model

- GIVEN a Flux 2 manifest references a model not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Turbo Toggle to Graph Behavior

The system MUST resolve `use_turbo` to a graph switch: when `true`, the Flux 2-Turbo LoRA (`Flux_2-Turbo-LoRA_comfyui.safetensors`) MUST be activated in the ComfyUI graph; when `false`, the base Flux 2 model runs without the Turbo LoRA. The switch MUST be resolved before graph execution.

#### Scenario: Turbo LoRA activated

- GIVEN `use_turbo = true`
- WHEN the workflow engine resolves the graph
- THEN the resolved graph includes the Flux 2-Turbo LoRA node

#### Scenario: Base model without Turbo LoRA

- GIVEN `use_turbo = false`
- WHEN the workflow engine resolves the graph
- THEN the resolved graph excludes the Turbo LoRA node

### Requirement: Resolve Base64 Image into Workflow

The system MUST decode `image_base64` and inject it into the workflow's `LoadImageFromBase64` node at execution time. The decoded image MUST be validated as a supported format (PNG, JPEG, WebP) before injection.

#### Scenario: Base64 image decoded and injected

- GIVEN a valid `image_base64` string encoding a PNG image
- WHEN the engine resolves parameters
- THEN the `LoadImageFromBase64` node receives the decoded image

#### Scenario: Unsupported image format rejected

- GIVEN `image_base64` encodes a BMP or TIFF image
- WHEN the engine validates the image
- THEN the request is rejected with `error.code = "invalid_image_base64"`
