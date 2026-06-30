# Delta for Image Generation

## ADDED Requirements

### Requirement: Orchestrated Generation Entry Point

The system MUST expose a prompt-first orchestration entry point that accepts a user prompt, optional selected asset identifiers, and optional workspace context. It SHALL return either a normal generation job response, a clarifying question, missing-asset guidance, or a typed error envelope.

#### Scenario: Orchestrated request accepted

- GIVEN a clear composition prompt and valid owned asset identifiers
- WHEN the orchestration entry point is called
- THEN the response is `202 Accepted` with `job_id` and `status = pending`
- AND lifecycle observation continues through the existing WebSocket contract

#### Scenario: Clarification response

- GIVEN the prompt is ambiguous or planner confidence is below threshold
- WHEN the orchestration entry point is called
- THEN no job is created
- AND the response includes one clarifying question for the user

#### Scenario: Missing asset response

- GIVEN the selected intent requires an asset role that was not provided
- WHEN the orchestration entry point is called
- THEN no job is created
- AND the response names the missing asset role and suggests upload or selection

### Requirement: Orchestration Dispatch Safety

The system MUST validate planner output against an allowlist of typed workflow names, declared parameter schemas, and owned asset identifiers before dispatch. The system MUST NOT pass raw LLM graph data to the workflow engine or Modal tasks.

#### Scenario: Valid plan dispatches typed flow

- GIVEN a schema-valid plan targets `extraction`, `composition`, `identity`, or Flux 2 workflow behavior
- WHEN workflow and asset validation succeed
- THEN existing typed flow execution is used without changing job lifecycle semantics

#### Scenario: Unsafe plan rejected

- GIVEN planner output includes an unapproved workflow, undeclared parameter, or raw ComfyUI graph node
- WHEN validation runs
- THEN execution is blocked with a typed validation error
