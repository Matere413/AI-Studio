# Proposal: Fix Orchestrator Selected Assets

## Intent

Fix selected-asset orchestration semantics so the agent treats user selection as a strict contract, maps selected assets to required workflow roles reliably, and blocks unsafe generation when selected assets are ambiguous, unavailable, failed, or unselected.

## Scope

### In Scope
- Enrich orchestration requests/planning context with selected asset metadata, not opaque IDs only.
- Auto-assign one selected asset when a one-asset role is required.
- Require explicit background/foreground intent for two-asset composition; otherwise ask clarification.
- Ask clarification for multi-asset identity/reference-face and extraction/input-image ambiguity.
- Block generation for selected assets still uploading or failed, with clear user guidance.
- Fix stale orchestration request dependencies for workflow hint and turbo state.
- Add a development-plan item for future `flux2_editing` selected-asset integration.

### Out of Scope
- UX redesign beyond recognition/selection semantics.
- Using assets that were not selected by the user.
- Server-side asset lookup redesign unless needed for validation.
- `flux2_editing` integration in this change.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `orchestrator-agent`: selected assets become a strict planning and dispatch contract with metadata-aware role assignment, ambiguity clarification, and unavailable-asset blocking.

## Approach

Extend the current client-plus-API enrichment path: send structured summaries for selected assets, update planner instructions/schema validation around role assignment, preserve typed executor boundaries, and keep backend validation strict against the selected asset set.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `view/src/app/page.tsx` | Modified | Request assembly and stale callback dependencies. |
| `view/src/features/chat/application/build-generate-request.ts` | Modified | Include selected asset metadata in orchestration DTO. |
| `api/src/features/generation/models.py` | Modified | Request/planner schemas for selected asset summaries. |
| `api/src/features/generation/planner.py` | Modified | Planner prompt/context role rules. |
| `api/src/features/generation/orchestrator.py` | Modified | Strict selected-asset validation and clarification/blocking. |
| `openspec/development-plan.md` | Modified | Future `flux2_editing` integration item. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Planner still guesses roles | Med | Use explicit role rules and block/clarify on ambiguity. |
| DTO drift across client/server | Med | Cover builder, schema, and orchestrator tests together. |
| Over-scoping into UX redesign | Low | Limit copy/UI changes to guidance states only. |

## Rollback Plan

Revert the proposal change set and restore the previous orchestration DTO/planner behavior. Since no persistence format changes are planned, rollback should not require data migration.

## Dependencies

- Existing asset selection state and atomic flows: `extraction`, `composition`, `identity`.

## Success Criteria

- [ ] Selected assets are the only assets eligible for planning and dispatch.
- [ ] Ambiguous multi-asset cases ask clarification instead of guessing.
- [ ] Uploading/failed selected assets block generation with actionable guidance.
- [ ] `flux2_editing` selected-asset support is tracked as future work.
