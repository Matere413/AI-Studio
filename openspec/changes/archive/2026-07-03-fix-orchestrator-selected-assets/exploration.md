## Exploration: fix-orchestrator-selected-assets

### Current State
Asset selection starts in `view/src/features/assets/presentation/components/AssetList.tsx` and `AssetsDrawer.tsx`, where completed uploads can be toggled into `selectedAssetIds`. `view/src/app/page.tsx` then submits only those IDs, plus `workspaceContext`, `workflowHint`, and `useTurbo`, through `buildOrchestrateRequest()` to `/generate/orchestrate`.

On the backend, `api/src/features/generation/planner.py` forwards only `prompt`, `selected_asset_ids`, `workspace_context`, and optional `workflow_hint` to the planner provider. The planner must infer `asset_roles` from opaque IDs and prompt text alone. `api/src/features/generation/orchestrator.py` then rejects requests when required roles are missing or when planned `asset_roles` are not present in the raw selected ID set.

The current `handleSend` callback in `view/src/app/page.tsx` omits `selectedWorkflow` and `useTurbo` from its dependency array, so orchestration hints can be stale even when the UI state changes.

### Affected Areas
- `view/src/app/page.tsx` — orchestration request assembly and stale hook dependencies.
- `view/src/features/chat/application/build-generate-request.ts` — request DTO builder for orchestration payloads.
- `view/src/features/assets/presentation/components/AssetList.tsx` — selection UI that feeds orchestration context.
- `view/src/features/assets/presentation/components/AssetsDrawer.tsx` — selection/upload wiring.
- `view/src/features/assets/application/use-upload.ts` — upload finalization updates asset IDs used by selection.
- `api/src/features/generation/models.py` — `OrchestrateRequest` / `PlannerDecision` schemas.
- `api/src/features/generation/planner.py` — planner context currently lacks asset metadata.
- `api/src/features/generation/orchestrator.py` — asset-role validation and missing-asset enforcement.
- `api/src/tests/test_orchestrator_agent.py` — backend behavior coverage for planning/validation.
- `view/src/features/chat/application/__tests__/build-generate-request.test.ts` — request builder coverage.

### Approaches
1. **Enrich orchestration context at the client boundary** — send selected asset summaries/metadata alongside IDs, and keep backend validation typed.
   - Pros: planner can map roles with names/types, minimal backend coupling, keeps current typed-dispatch model intact.
   - Cons: requires DTO and planner-prompt updates; still needs server-side ownership checks.
   - Effort: Medium

2. **Derive asset context server-side before planning** — resolve selected IDs into asset records in the API, then pass structured asset context to the planner.
   - Pros: single trust boundary, avoids relying on client-provided metadata, easier to enforce ownership.
   - Cons: adds backend lookups/coupling, more plumbing in the orchestration path, broader API/service change.
   - Effort: High

### Recommendation
Use the client-plus-API enrichment path: add structured selected-asset context to the orchestration request, keep the orchestrator’s typed asset-role validation, and fix the stale `handleSend` dependencies in the same change. That directly addresses the current failure mode without weakening the existing safety checks.

### Risks
- Planner/provider prompts may still mis-map roles if the added context is too sparse or inconsistent.
- Any request-shape change must stay aligned across frontend DTOs, backend models, and tests.
- The stale dependency bug can continue to produce confusing behavior if it is not bundled with the asset-context fix.

### Ready for Proposal
Yes — propose a scoped change to enrich orchestration context with selected asset metadata/role hints, update planner/orchestrator validation accordingly, and fix the stale `handleSend` dependency array.
