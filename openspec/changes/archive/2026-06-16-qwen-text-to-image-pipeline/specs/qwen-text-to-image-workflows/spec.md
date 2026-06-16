# Qwen Text-to-Image Workflows Specification

## Purpose

Define the contract for the Qwen Image text-to-image workflow: dynamic dimensions, quality-mode behavior, and the simplified template format without custom switch/primitive nodes.

## Requirements

### Requirement: Accept Qwen Workflow Selection

The system MUST accept `workflow = "qwen_txt2img"` as a valid workflow identifier on `POST /generate`. The request MUST include `prompt` (required, non-empty string) and MAY include `negative_prompt`, `width`, `height`, and `quality_mode`.

#### Scenario: Qwen workflow request accepted

- GIVEN a client sends `workflow = "qwen_txt2img"` with a valid `prompt`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Qwen workflow with all optional parameters

- GIVEN a client sends `workflow = "qwen_txt2img"` with `prompt`, `negative_prompt`, `width`, `height`, and `quality_mode`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and all parameters are recorded

### Requirement: Validate Dynamic Dimensions

The system MUST validate that `width` and `height` are integers, multiples of 64, within the range [256, 2048], and their product MUST NOT exceed 4,194,304 pixels (~2048×2048). Invalid dimensions MUST be rejected with HTTP 400 and `error.code = "invalid_dimensions"`.

#### Scenario: Valid dimensions accepted

- GIVEN `width = 1024` and `height = 1024`
- WHEN `POST /generate` is called
- THEN the request proceeds to execution

#### Scenario: Non-multiple of 64 rejected

- GIVEN `width = 1000`
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "invalid_dimensions"`

#### Scenario: Out-of-range dimension rejected

- GIVEN `width = 4096`
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "invalid_dimensions"`

#### Scenario: Pixel budget exceeded rejected

- GIVEN `width = 2048` and `height = 2048` (product = 4,194,304, at limit)
- WHEN `POST /generate` is called
- THEN the request proceeds to execution

- GIVEN `width = 2048` and `height = 2560` (product = 5,242,880, over limit)
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "invalid_dimensions"`

### Requirement: Quality Mode Controls Sampler Defaults

The system MUST support two quality modes: `"fast"` (Lightning LoRA path, 4 steps, CFG 1.5, sampler `euler`, scheduler `sgm_uniform`) and `"high"` (full model path, 50 steps, CFG 7.0, sampler `euler_ancestral`, scheduler `normal`). The default quality mode MUST be `"high"`. Invalid mode values MUST be rejected with HTTP 400 and `error.code = "invalid_quality_mode"`.

#### Scenario: Fast mode selects Lightning path

- GIVEN `quality_mode = "fast"`
- WHEN the workflow executes
- THEN the Lightning LoRA is applied with 4 steps, CFG 1.5, sampler `euler`

#### Scenario: High mode uses full model

- GIVEN `quality_mode = "high"` (or omitted)
- WHEN the workflow executes
- THEN the full Qwen model runs with 50 steps, CFG 7.0, sampler `euler_ancestral`

#### Scenario: Invalid quality mode rejected

- GIVEN `quality_mode = "ultra"`
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "invalid_quality_mode"`

### Requirement: Qwen Template Uses Simplified Format

The Qwen workflow template MUST NOT include custom switch or primitive nodes from the source workflow. All conditional logic (quality mode branching) MUST be resolved by the workflow engine before sending the graph to ComfyUI.

#### Scenario: Template loads without custom nodes

- GIVEN the Qwen template is loaded
- WHEN the template is validated
- THEN no custom switch/primitive node class_types are present

#### Scenario: Quality mode resolved before execution

- GIVEN `quality_mode = "fast"`
- WHEN the workflow engine resolves the graph
- THEN the resolved graph contains only the Lightning LoRA path nodes
