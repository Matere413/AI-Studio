# Delta for Image Generation

## ADDED Requirements

### Requirement: Accept Product Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "product_premium"` and a free-form `prompt`. When `workflow = "product_premium"`, the request MAY include an optional `format` field with values `"square"` or `"vertical"` (default: `"square"`). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Product workflow request accepted

- GIVEN a client sends `prompt` and `workflow = "product_premium"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Product workflow with vertical format

- GIVEN a client sends `prompt`, `workflow = "product_premium"`, and `format = "vertical"`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and the vertical format is recorded

#### Scenario: Product workflow with invalid format rejected

- GIVEN a client sends `workflow = "product_premium"` and `format = "panoramic"`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error
