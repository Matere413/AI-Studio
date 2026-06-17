# Delta for identity-gguf-workflows

## MODIFIED Requirements

### Requirement: Accept Identity GGUF Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "identidad_gguf"` and parameters: `prompt` (required, non-empty string), `image_url` (required, string — either a public HTTPS URL or a base64/data URL starting with `data:image/`), `width` (optional integer, multiple of 64, default from manifest), `height` (optional integer, multiple of 64, default from manifest), and `seed` (optional integer, -1 for random). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.
(Previously: `image_url` was described as "valid URL to reference identity image" without base64/data URL support.)

#### Scenario: Identity GGUF request accepted with HTTPS URL

- GIVEN a client sends `workflow = "identidad_gguf"` with `prompt` and `image_url` as `https://...`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Identity GGUF request accepted with base64 data URL

- GIVEN a client sends `workflow = "identidad_gguf"` with `prompt` and `image_url` as `data:image/png;base64,...`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Missing reference image rejected

- GIVEN a client sends `workflow = "identidad_gguf"` without `image_url`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Invalid image_url format rejected

- GIVEN a client sends `image_url` that is neither a valid URL nor a valid data URL
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error for `image_url`
