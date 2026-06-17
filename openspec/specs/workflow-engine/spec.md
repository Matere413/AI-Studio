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

The system MUST apply runtime parameters through the manifest and execute the resolved workflow. The system SHALL support at least text-to-image, image-to-image, and ControlNet workflows through the same execution contract.

#### Scenario: Execute text-to-image workflow

- GIVEN a text-to-image template and valid prompt parameters
- WHEN the engine executes the workflow
- THEN ComfyUI receives a resolved graph for that template

#### Scenario: Execute image-conditional workflow

- GIVEN an image-to-image or ControlNet template and required image inputs
- WHEN the engine executes the workflow
- THEN the resolved graph includes the referenced image-conditioned parameters

### Requirement: Load Product Premium Workflow Manifest

The system MUST load the `product_premium` workflow template and manifest from `api/src/workflows/product_premium/`. The manifest MUST declare `prompt` (required, free-form text) and `format` (optional, enum: `["square", "vertical"]`) as supported parameters. The engine MUST validate that the manifest's referenced checkpoint is in the approved whitelist before loading.

#### Scenario: Product premium workflow loads

- GIVEN the `product_premium` directory contains a valid template and manifest
- WHEN the workflow engine loads the `product_premium` workflow
- THEN the engine returns a parameterizable definition with `prompt` and `format` parameters

#### Scenario: Product manifest references non-whitelisted checkpoint

- GIVEN the `product_premium` manifest references a checkpoint not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Product-Specific Parameters

The system MUST resolve `format` parameter values to T4-safe resolutions: `square` maps to a 1:1 resolution and `vertical` maps to a 9:16 resolution. The resolution values MUST be defined in the manifest, not hardcoded in the engine.

#### Scenario: Square format resolves to correct resolution

- GIVEN a `product_premium` request with `format = "square"`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph receives the 1:1 resolution from the manifest

#### Scenario: Vertical format resolves to correct resolution

- GIVEN a `product_premium` request with `format = "vertical"`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph receives the 9:16 resolution from the manifest

#### Scenario: Default format applied when omitted

- GIVEN a `product_premium` request without a `format` field
- WHEN the engine resolves parameters
- THEN the engine applies the default `square` resolution from the manifest

### Requirement: Load Realistic Persona Workflow Manifest

The system MUST load the `realistic_persona` workflow template and manifest from `api/src/workflows/realistic_persona/`. The manifest MUST declare `prompt` (required, free-form text) and persona controls (`age`, `gender`, `ethnicity`, `wardrobe`, `expression`, `background`) as supported parameters. The engine MUST validate that the manifest's referenced checkpoint is in the approved whitelist before loading.

#### Scenario: Realistic persona workflow loads

- GIVEN the `realistic_persona` directory contains a valid template and manifest
- WHEN the workflow engine loads the `realistic_persona` workflow
- THEN the engine returns a parameterizable definition with all declared persona controls

#### Scenario: Persona manifest references non-whitelisted checkpoint

- GIVEN the `realistic_persona` manifest references a checkpoint not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Persona-Specific Parameters

The system MUST resolve persona control values into the ComfyUI graph through the manifest. Resolution values MUST be defined in the manifest, not hardcoded in the engine. The engine MUST apply default values for unspecified persona controls.

#### Scenario: Persona controls resolve to graph parameters

- GIVEN a `realistic_persona` request with `age`, `gender`, and `wardrobe`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph receives resolved values from the manifest for each control

#### Scenario: Default persona controls applied

- GIVEN a `realistic_persona` request with only `prompt`
- WHEN the engine resolves parameters
- THEN default values from the manifest are applied for all unspecified persona controls

### Requirement: Load Qwen Text-to-Image Workflow Manifest

The system MUST load the `qwen_txt2img` workflow template and manifest from `api/src/workflows/qwen_txt2img/`. The manifest MUST declare `prompt` (required, free-form text), `negative_prompt` (optional string), `width` (optional integer, multiple of 64, 256-2048), `height` (optional integer, multiple of 64, 256-2048), and `quality_mode` (optional enum: `["fast", "high"]`, default `"high"`) as supported parameters. The engine MUST validate that the manifest's referenced Qwen FP8 UNET, Qwen CLIP, and Qwen VAE are in the approved whitelist before loading.

#### Scenario: Qwen workflow loads successfully

- GIVEN the `qwen_txt2img` directory contains a valid template and manifest
- WHEN the workflow engine loads the `qwen_txt2img` workflow
- THEN the engine returns a parameterizable definition with all declared parameters

#### Scenario: Qwen manifest references non-whitelisted model

- GIVEN the `qwen_txt2img` manifest references a Qwen UNET not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Qwen Dimensions and Quality Mode

The system MUST resolve `width` and `height` values from the request, falling back to manifest defaults when omitted. The system MUST resolve `quality_mode` to sampler/step/CFG defaults: `"fast"` maps to 4 steps, CFG 1.5, Lightning LoRA enabled; `"high"` maps to 50 steps, CFG 7.0, Lightning LoRA disabled. Resolution values MUST be defined in the manifest, not hardcoded in the engine.

#### Scenario: Custom dimensions resolve correctly

- GIVEN a `qwen_txt2img` request with `width = 768` and `height = 1024`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph receives width 768 and height 1024

#### Scenario: Default dimensions applied when omitted

- GIVEN a `qwen_txt2img` request without `width` or `height`
- WHEN the engine resolves parameters
- THEN the engine applies default dimensions from the manifest

#### Scenario: Fast quality mode resolves to Lightning path

- GIVEN a `qwen_txt2img` request with `quality_mode = "fast"`
- WHEN the engine resolves parameters
- THEN the resolved graph includes Lightning LoRA with 4 steps and CFG 1.5

#### Scenario: High quality mode resolves to full path

- GIVEN a `qwen_txt2img` request with `quality_mode = "high"`
- WHEN the engine resolves parameters
- THEN the resolved graph uses the full Qwen model with 50 steps and CFG 7.0, no Lightning LoRA

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
