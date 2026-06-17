# Workflow Engine Specification

## Purpose

Define how ComfyUI Studio parses workflow templates plus manifests and executes parameterized workflows without coupling API code to exported node IDs.

## Requirements

### Requirement: Parse Hybrid Template and Node Map

The system MUST load a static ComfyUI API-format template together with a manifest that maps semantic inputs to node targets. The system MUST reject a workflow when a required manifest entry, node, or field reference is missing.

#### Scenario: Template and manifest are valid

- GIVEN a stored template and matching manifest
- WHEN the workflow is loaded
- THEN the engine returns a parameterizable workflow definition

#### Scenario: Manifest references an invalid node

- GIVEN a manifest points to a missing node or field
- WHEN the workflow is loaded
- THEN the engine rejects the workflow with a validation error

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

<!-- Requirements removed in refactor-flux-api:
  - Load Product Premium Workflow Manifest → retired, workflow removed
  - Resolve Product-Specific Parameters → retired, workflow removed
  - Load Realistic Persona Workflow Manifest → retired, workflow removed
  - Resolve Persona-Specific Parameters → retired, workflow removed
  - Load Qwen Text-to-Image Workflow Manifest → retired, workflow removed
  - Resolve Qwen Dimensions and Quality Mode → retired, workflow removed
-->

### Requirement: Load Identity GGUF Workflow Manifest

The system MUST load the `identidad_gguf` workflow template and manifest from `api/src/workflows/identidad_gguf/`. The manifest MUST declare `prompt` (required), `image_url` (required), `width` (optional), `height` (optional), and `seed` (optional) as supported parameters. The engine MUST validate that the manifest's referenced GGUF UNET, CLIP, PuLID, and face detector models are in the approved whitelist before loading.

#### Scenario: Identity GGUF workflow loads

- GIVEN the `identidad_gguf` directory contains a valid template and manifest
- WHEN the workflow engine loads the `identidad_gguf` workflow
- THEN the engine returns a parameterizable definition with all declared parameters

#### Scenario: Identity GGUF manifest references non-whitelisted model

- GIVEN the `identidad_gguf` manifest references a GGUF UNET not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Identity GGUF Parameters

The system MUST resolve `image_url` to a runtime-downloadable reference image and inject it into the workflow's `LoadImage` node (or equivalent image-input node) at execution time. The system MUST resolve `width` and `height` from the request, falling back to manifest defaults. The system MUST resolve `seed` to an integer, generating a random seed when `-1` or omitted.

#### Scenario: Reference image injected into workflow

- GIVEN an `identidad_gguf` request with a valid `image_url`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph's image-input node receives the downloaded reference image

#### Scenario: Default dimensions applied

- GIVEN an `identidad_gguf` request without `width` or `height`
- WHEN the engine resolves parameters
- THEN the engine applies default dimensions from the manifest
