# Proposal: SDD 4 Orchestrator Agent

## Intent

Add a prompt-first orchestrator so designers, marketers, and operators can request outcomes without choosing technical workflows. The backend already executes typed ComfyUI flows; the gap is safe intent planning, asset-role mapping, clarification, and staged UX visibility.

## Scope

### In Scope
- Strict JSON planner: intent, `workflow_name`, asset roles, params, confidence, clarification/missing-asset prompt.
- Backend validation and dispatch to approved typed flows: extraction, composition, identity/persona, Flux 2 editing/text.
- Frontend prompt-first contract with step timeline, clarifying questions, and missing-asset guidance.

### Out of Scope
- LLM-generated ComfyUI graphs.
- New model training, workflows, or raw prompt-engineering controls.
- Multi-turn autonomous campaign planning beyond one generation/editing request.

## Capabilities

### New Capabilities
- `orchestrator-agent`: prompt-to-plan routing, clarification, missing-asset handling, and typed flow dispatch.

### Modified Capabilities
- `image-generation`: add an orchestration entrypoint while preserving typed flow execution and job lifecycle semantics.
- `generative-ai-studio-frontend`: replace manual workflow-first submission with prompt-first agent UX, stage visibility, and stale `identidad_gguf` contract cleanup.

## Approach

Use **Structured LLM Planner + Typed Executor**. The LLM emits only a schema-validated plan. The service validates confidence, assets, workflow allowlist, params, and ownership through the existing resolver, then calls current typed dispatch.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/features/generation/router.py` | Modified | Add orchestration entrypoint. |
| `api/src/features/generation/service.py` | Modified | Planner, validation, clarification/missing-asset responses. |
| `api/src/shared/flows/*` | Modified | Planner target schemas only; execution remains typed. |
| `api/src/shared/workflows/engine.py` | Unchanged | Remains graph executor, not planner. |
| `api/app.py` | Modified | Reuse asset resolver wiring. |
| `view/src/features/chat/...` | Modified | Prompt-first request, stages, questions. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Wrong or unsafe LLM route | Med | Strict schema, allowlist, confidence threshold, clarification fallback. |
| Missing/unauthorized assets | Med | Resolve only owned `asset_id`; ask user to upload/select missing assets. |
| Frontend/backend workflow drift | High | Remove stale `identidad_gguf` assumptions during contract update. |

## Rollback Plan

Disable the orchestration endpoint/UI path and keep existing typed generation endpoints unchanged. Revert frontend to manual workflow submission while preserving uploaded assets and job lifecycle handling.

## Dependencies

- Configured LLM provider/model for planner calls.
- Existing typed flow registry, asset resolver, Modal dispatch, and WebSocket lifecycle.

## Success Criteria

- [ ] Ambiguous prompts return a clarifying question instead of executing.
- [ ] Missing required assets return upload/select guidance.
- [ ] Valid core intents route to typed flows and return normal job lifecycle updates.
- [ ] UI shows visible planning/execution stages before final image.
