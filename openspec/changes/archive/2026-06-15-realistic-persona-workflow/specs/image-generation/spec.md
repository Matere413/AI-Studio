# Delta for Image Generation

## ADDED Requirements

### Requirement: Accept Realistic Persona Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "realistic_persona"` and declared persona controls: `age` (integer, 18-100), `gender` (enum), `ethnicity` (enum), `wardrobe` (free-form text), `expression` (free-form text), and `background` (free-form text). The system MUST reject requests with undeclared controls or values outside declared ranges. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Persona workflow request accepted

- GIVEN a client sends `workflow = "realistic_persona"` with valid persona controls
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Undeclared control rejected

- GIVEN a client sends `workflow = "realistic_persona"` with an undeclared control `hair_color`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Age out of range rejected

- GIVEN a client sends `age = 5` for `realistic_persona`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error for age range
