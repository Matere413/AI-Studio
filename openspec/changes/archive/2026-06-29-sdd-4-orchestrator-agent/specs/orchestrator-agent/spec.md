# Orchestrator Agent Specification

## Purpose

Define prompt-to-plan orchestration for generation and editing requests while preserving typed workflow execution.

## Requirements

### Requirement: Structured Planning

The system MUST convert a user prompt plus selected assets into a schema-validated plan containing intent, workflow name, asset roles, parameters, confidence, and either execution readiness or a blocking question.

#### Scenario: Valid product extraction plan

- GIVEN a prompt requesting product extraction and a selected product image asset
- WHEN the orchestrator plans the request
- THEN it returns a valid plan targeting an approved extraction workflow
- AND maps the selected asset to the required product image role

#### Scenario: Malformed planner output rejected

- GIVEN the planner returns output that does not match the schema
- WHEN the system validates the plan
- THEN the request MUST NOT execute
- AND the user receives a safe planning failure response

### Requirement: Clarification Before Execution

The system MUST ask one clarifying question when intent, workflow, or required parameters are ambiguous or confidence is below the execution threshold.

#### Scenario: Ambiguous request asks question

- GIVEN a prompt such as "make it better" with insufficient context
- WHEN the orchestrator evaluates the request
- THEN it returns a clarifying question instead of creating a job

#### Scenario: Confident request proceeds

- GIVEN a clear prompt with all required inputs
- WHEN confidence meets the threshold
- THEN the orchestrator MAY proceed to dispatch after validation

### Requirement: Missing Asset Guidance

The system MUST identify missing required asset roles and return upload or select-asset guidance instead of dispatching incomplete workflows.

#### Scenario: Identity request missing reference

- GIVEN a prompt asking to preserve a person's identity without a reference asset
- WHEN the orchestrator plans the request
- THEN it returns a missing-asset response naming the required identity reference
- AND suggests uploading or selecting an existing asset

#### Scenario: Unauthorized asset rejected

- GIVEN a plan references an asset not owned by the current workspace/user
- WHEN asset validation runs
- THEN the request MUST NOT execute
- AND the response indicates the asset must be selected again

### Requirement: Typed Executor Boundary

The system MUST dispatch only to approved typed flows for extraction, composition, identity/persona, Flux 2 editing, or Flux 2 text generation. It MUST NOT execute LLM-generated ComfyUI graphs.

#### Scenario: Approved typed flow dispatched

- GIVEN a valid plan for composition with required assets
- WHEN validation succeeds
- THEN the existing typed generation dispatch is invoked
- AND the normal job lifecycle is returned

#### Scenario: Raw graph plan blocked

- GIVEN planner output includes raw ComfyUI nodes or an unapproved workflow
- WHEN validation runs
- THEN the plan is rejected before execution
