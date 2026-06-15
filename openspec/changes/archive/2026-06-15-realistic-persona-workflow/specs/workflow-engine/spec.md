# Delta for Workflow Engine

## ADDED Requirements

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
