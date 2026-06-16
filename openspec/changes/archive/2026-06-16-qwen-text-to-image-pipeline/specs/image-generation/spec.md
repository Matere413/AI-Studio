# Delta for Image Generation

## ADDED Requirements

### Requirement: Accept Qwen Text-to-Image Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "qwen_txt2img"` and parameters: `prompt` (required, non-empty string), `negative_prompt` (optional string), `width` (optional integer, default from manifest), `height` (optional integer, default from manifest), and `quality_mode` (optional enum: `["fast", "high"]`, default `"high"`). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Qwen workflow request accepted

- GIVEN a client sends `workflow = "qwen_txt2img"` with a valid `prompt`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Qwen workflow with custom dimensions and quality mode

- GIVEN a client sends `workflow = "qwen_txt2img"` with `width = 768`, `height = 1024`, `quality_mode = "fast"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and all parameters are recorded

#### Scenario: Qwen workflow with invalid workflow parameter rejected

- GIVEN a client sends `workflow = "qwen_txt2img"` with an undeclared parameter `seed_strategy`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error
