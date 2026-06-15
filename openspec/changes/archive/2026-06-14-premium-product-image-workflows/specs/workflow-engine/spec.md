# Delta for Workflow Engine

## ADDED Requirements

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
