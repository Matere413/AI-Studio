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
