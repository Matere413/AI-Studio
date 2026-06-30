# Delta for Generative AI Studio Frontend

## ADDED Requirements

### Requirement: Prompt-First Agent Submission

The system MUST make the chat prompt the primary submission control and SHALL send orchestration requests without requiring users to choose a technical workflow. Advanced manual workflow controls SHOULD NOT be visible in the default designer-facing path.

#### Scenario: Natural language request submitted

- GIVEN the user enters a prompt and optionally selects assets
- WHEN the user submits from the chat sidebar
- THEN the client sends an orchestration request with prompt and asset identifiers
- AND does not send stale manual workflow fields

#### Scenario: Designer-facing UI remains simple

- GIVEN the default studio experience renders
- WHEN no advanced mode is enabled
- THEN workflow selectors, model selectors, CFG, sampler, and raw parameter controls are hidden

### Requirement: Agent Stage Timeline

The system MUST show visible orchestration stages before the final image, including planning, validating assets, dispatching, generating, and completed or blocked states.

#### Scenario: Successful staged execution

- GIVEN an orchestration request is submitted
- WHEN the backend accepts and dispatches a job
- THEN the UI displays planning, validation, dispatch, and generation stages
- AND continues to use WebSocket lifecycle updates for execution progress

#### Scenario: Clarification stage

- GIVEN the backend returns a clarifying question
- WHEN the response is rendered
- THEN the timeline shows the request blocked at planning
- AND the question is displayed as the next user action

#### Scenario: Missing asset stage

- GIVEN the backend returns missing-asset guidance
- WHEN the response is rendered
- THEN the timeline shows the request blocked at asset validation
- AND the UI suggests uploading or selecting the required asset role

### Requirement: Orchestration Client Contract

The client MUST normalize orchestration outcomes into one of: `job_started`, `clarification_required`, `missing_asset`, or `error`. It MUST remove deprecated `identidad_gguf` assumptions from the default prompt-first request builder.

#### Scenario: Job outcome normalized

- GIVEN the backend returns `job_id` and `status = pending`
- WHEN the client parses the response
- THEN UI state transitions into execution monitoring

#### Scenario: Deprecated contract not sent

- GIVEN a user asks for identity/persona preservation
- WHEN the client submits the orchestration request
- THEN it sends selected asset identifiers and prompt context
- AND it MUST NOT require or send `identidad_gguf` as a manual workflow choice

## MODIFIED Requirements

### Requirement: Chat Sidebar

The system MUST provide a chat sidebar with scrollable message history at the top, a prompt input bar at the bottom, selected-asset context, and submission via Enter or send button. The default sidebar MUST NOT require a manual workflow dropdown before submission.
(Previously: The chat sidebar included a manual workflow dropdown and speed selector as default controls.)

#### Scenario: Prompt submission
- GIVEN a valid prompt and optional selected assets
- WHEN the user presses Enter or the send button
- THEN the message is appended to history and an orchestration request is dispatched

#### Scenario: Empty prompt blocked
- GIVEN prompt empty/whitespace
- THEN send is disabled with inline error "Prompt is required"

## REMOVED Requirements

### Requirement: Manual Workflow Selector

(Reason: The default experience becomes prompt-first orchestration rather than manual workflow-first selection.)
(Migration: Replace default workflow selection with orchestration outcomes and hidden/advanced typed controls when needed.)
