# Delta for Workflow Engine

## ADDED Requirements

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
