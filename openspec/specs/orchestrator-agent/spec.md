# Orchestrator Agent Specification

## Purpose

Define prompt-to-plan orchestration for generation and editing requests while preserving typed workflow execution.

## Requirements

### Requirement: Structured Planning

The system MUST convert a user prompt plus selected assets into a schema-validated plan containing intent, workflow name, asset roles, parameters, confidence, and either execution readiness or a blocking question. Selected assets MUST be treated as a strict contract: planning and dispatch MUST NOT use assets outside the selected set. Planner context MUST include selected asset metadata sufficient for role reasoning, such as identifier, name, status, media type, and available descriptive fields.

#### Scenario: Valid product extraction plan

- GIVEN a prompt requesting product extraction and one selected completed product image asset
- WHEN the orchestrator plans the request
- THEN it returns a valid plan targeting an approved extraction workflow
- AND maps the selected asset to the required product image role

#### Scenario: Planner cannot use unselected assets

- GIVEN selected assets omit an asset mentioned in workspace context
- WHEN the orchestrator plans and validates the request
- THEN the request MUST NOT execute using the unselected asset
- AND the response asks the user to select the required asset

#### Scenario: Malformed planner output rejected

- GIVEN the planner returns output that does not match the schema
- WHEN the system validates the plan
- THEN the request MUST NOT execute
- AND the user receives a safe planning failure response

### Requirement: Clarification Before Execution

The system MUST ask one clarifying question when intent, workflow, required role mapping, or required parameters are ambiguous, or when confidence is below the execution threshold. Composition MUST require explicit role mapping for background and foreground assets, unless the prompt and selected metadata make the mapping unambiguous. Identity and extraction requests with multiple candidate selected assets MUST ask clarification instead of guessing.

#### Scenario: Ambiguous request asks question

- GIVEN a prompt such as "make it better" with insufficient context
- WHEN the orchestrator evaluates the request
- THEN it returns a clarifying question instead of creating a job

#### Scenario: Composition without role mapping asks question

- GIVEN two selected completed assets and a composition prompt without background or foreground intent
- WHEN the orchestrator evaluates the request
- THEN it asks which asset is background and which is foreground

#### Scenario: Multiple identity candidates ask question

- GIVEN multiple selected completed person/reference assets
- WHEN the prompt asks to preserve identity without identifying the reference
- THEN the orchestrator asks which selected asset to use as the identity reference

#### Scenario: Confident request proceeds

- GIVEN a clear prompt with all required inputs and unambiguous selected-asset roles
- WHEN confidence meets the threshold
- THEN the orchestrator MAY proceed to dispatch after validation

### Requirement: Missing Asset Guidance

The system MUST identify missing, unavailable, uploading, or failed required asset roles and return clear guidance instead of dispatching incomplete workflows. Uploading assets MUST block generation until upload completes; failed assets MUST block generation with retry, remove, or re-upload guidance.

#### Scenario: Identity request missing reference

- GIVEN a prompt asking to preserve a person's identity without a reference asset
- WHEN the orchestrator plans the request
- THEN it returns a missing-asset response naming the required identity reference
- AND suggests uploading or selecting an existing asset

#### Scenario: Uploading selected asset blocks generation

- GIVEN a required selected asset is still uploading
- WHEN validation runs
- THEN the request MUST NOT execute
- AND the response tells the user to wait for upload completion

#### Scenario: Failed selected asset blocks generation

- GIVEN a required selected asset has failed processing
- WHEN validation runs
- THEN the request MUST NOT execute
- AND the response tells the user to retry, remove, or re-upload the asset

#### Scenario: Unauthorized asset rejected

- GIVEN a plan references an asset not owned by the current workspace/user
- WHEN asset validation runs
- THEN the request MUST NOT execute
- AND the response indicates the asset must be selected again

### Requirement: Typed Executor Boundary

The system MUST dispatch only to the current approved atomic flows: extraction, composition, and identity. It MUST NOT execute LLM-generated ComfyUI graphs, and flux2_editing selected-asset integration MUST remain out of scope for this change and be tracked as future work.

#### Scenario: Approved atomic flow dispatched

- GIVEN a valid plan for extraction, composition, or identity with required selected assets
- WHEN validation succeeds
- THEN the matching typed generation dispatch is invoked
- AND the normal job lifecycle is returned

#### Scenario: Raw graph or future flow blocked

- GIVEN planner output includes raw ComfyUI nodes, an unapproved workflow, or flux2_editing
- WHEN validation runs
- THEN the plan is rejected before execution
