# Delta for Workflow Engine

## ADDED Requirements

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
