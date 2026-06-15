# Premium Product Image Workflows Specification

## Purpose

Define the contract for generating high-quality commercial product imagery (studio and lifestyle) via a dedicated `product_premium` ComfyUI workflow, with prompt-first input, square and vertical output formats, and T4-safe resolution defaults.

## Requirements

### Requirement: Product Premium Workflow Contract

The system MUST support a `product_premium` workflow that accepts a free-form text prompt describing a commercial physical product and generates studio-quality or lifestyle/in-context product imagery. The workflow MUST use a whitelisted premium checkpoint and tuned sampler/CFG/resolution defaults optimized for T4 GPUs.

#### Scenario: Studio product shot from prompt

- GIVEN a free-form prompt describing a physical product (e.g., "white ceramic mug on marble surface, studio lighting")
- WHEN the `product_premium` workflow is executed
- THEN a high-quality studio-style product image is generated using the premium checkpoint

#### Scenario: Lifestyle/in-context product shot from prompt

- GIVEN a free-form prompt describing a product in a real-world context (e.g., "running shoes on a forest trail at golden hour")
- WHEN the `product_premium` workflow is executed
- THEN a lifestyle/in-context product image is generated

#### Scenario: Prompt-only fidelity disclaimer

- GIVEN the workflow is prompt-only (no reference image)
- WHEN the generated image is delivered
- THEN the output reflects the prompt intent but does NOT guarantee exact product fidelity

### Requirement: Output Format Selection

The system MUST support two output formats for the `product_premium` workflow: `square` (1:1) and `vertical` (9:16 for social media). The default format MUST be `square`. Resolutions MUST be T4-safe (no A100-only sizes).

#### Scenario: Square output requested

- GIVEN a product request specifies `format = "square"`
- WHEN the workflow executes
- THEN the output image has a 1:1 aspect ratio at a T4-safe resolution

#### Scenario: Vertical output requested

- GIVEN a product request specifies `format = "vertical"`
- WHEN the workflow executes
- THEN the output image has a 9:16 aspect ratio at a T4-safe resolution

#### Scenario: Default format applied

- GIVEN a product request does not specify a format
- WHEN the workflow executes
- THEN the output image uses the `square` format by default

#### Scenario: Invalid format rejected

- GIVEN a product request specifies an unsupported format (e.g., "panoramic")
- WHEN the request is validated
- THEN the request is rejected with a validation error

### Requirement: Workflow Manifest and Parameters

The system MUST provide a `product_premium` workflow manifest that declares supported parameters (prompt, format) and maps them to ComfyUI node targets. The manifest MUST reference only whitelisted, pre-cached model identifiers.

#### Scenario: Workflow manifest loads successfully

- GIVEN the `product_premium` workflow directory contains a valid template and manifest
- WHEN the workflow engine loads the manifest
- THEN the engine resolves all parameter-to-node mappings without errors

#### Scenario: Missing checkpoint in manifest

- GIVEN the manifest references a checkpoint not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects the workflow with a validation error

### Requirement: Backward Compatibility

The system MUST ensure that existing generation clients and workflows continue to function unchanged when the `product_premium` workflow is added. Product workflow requests MUST NOT affect non-product workflow execution.

#### Scenario: Existing workflow unaffected

- GIVEN an existing txt2img request is submitted
- WHEN the request is processed
- THEN it executes the original workflow, not the product premium workflow

#### Scenario: Product workflow isolated

- GIVEN a `product_premium` request fails
- WHEN the failure occurs
- THEN other active generation jobs are not affected
