# Delta for Image Generation

## ADDED Requirements

### Requirement: Accept Identity GGUF Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "identidad_gguf"` and parameters: `prompt` (required, non-empty string), `image_url` (required, valid URL to reference identity image), `width` (optional integer, multiple of 64, default from manifest), `height` (optional integer, multiple of 64, default from manifest), and `seed` (optional integer, -1 for random). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Identity GGUF request accepted

- GIVEN a client sends `workflow = "identidad_gguf"` with `prompt` and `image_url`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Missing reference image rejected

- GIVEN a client sends `workflow = "identidad_gguf"` without `image_url`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Invalid image_url format rejected

- GIVEN a client sends `image_url` that is not a valid URL
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error
