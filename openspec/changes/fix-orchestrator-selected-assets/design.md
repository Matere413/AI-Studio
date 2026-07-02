# Design: Fix Orchestrator Selected Assets

## Technical Approach

Keep `selected_asset_ids` as the canonical contract, add optional `selected_assets` only as planner context, and make backend validation authoritative before dispatch. Because the current `Asset` row is created before upload completion and has no readiness field, this change adds trusted asset readiness to persistence and validates it in the orchestrator/resolver path. Scope remains `extraction`, `composition`, and `identity`; `flux2_editing` is out of implementation scope.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Canonical selection | `selected_asset_ids` remains authoritative; `selected_assets` is metadata only. | Replace IDs with summaries. | IDs are stable and enforceable; client metadata can be stale or forged. |
| Trusted readiness | Add server-owned asset readiness (`upload_status` + `finalized_at`) and set it only from upload-ticket/finalize backend paths. | Trust client `status`; object HEAD only. | DB status is deterministic and testable; HEAD can be optional defense-in-depth when storage is configured. |
| Validation placement | Normalize/validate selection pre-planner, then validate planner roles post-planner. | Planner-only checks. | Pre-checks stop invalid DTOs early; post-checks stop planner guesses or unselected assets. |
| Ambiguity | Single-candidate single-role flows may auto-map; multiple identity/extraction candidates or composition roles require explicit prompt intent. | Let high confidence override ambiguity. | LLM confidence must not guess user intent when selected assets admit multiple valid mappings. |
| Workflow scope | Atomic asset flows only; no `flux2_editing` implementation. | Bridge Flux 2 editing now. | Editing needs a separate asset-input contract and would over-scope this fix. |

## Data Flow

```text
Frontend selectedAssetIds + summaries
  → OrchestrateRequest
  → normalize IDs/summaries + trusted readiness lookup
  → planner context from normalized selected assets
  → PlannerDecision.asset_roles
  → post-planner selected-set/ambiguity/readiness validation
  → typed extraction/composition/identity dispatch
```

Validation order: schema parse → dedupe `selected_asset_ids` preserving order → reject summary IDs not selected → tolerate selected IDs missing summaries as legacy metadata-poor requests → trusted backend readiness lookup → pre-planner ambiguity guard where intent is impossible → planner → confidence/clarification → workflow allowlist → required roles → selected-set contract → resolver ownership/readability → post-planner ambiguity guard → dispatch.

## Security / Trust Boundary

Client `selected_assets.status`, names, tags, and descriptions are hints only. The backend MUST NOT use them for authorization, readiness, or readable-object proof. Trusted validation comes from `Asset` ownership, `deleted_at`, server-owned readiness fields, and optionally storage availability checks in `R2Storage` when configured.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/models/persistence.py` | Modify | Add server-owned `upload_status` and `finalized_at` fields to `Asset`. |
| `api/src/features/assets/service.py` | Modify | Create upload tickets as pending/uploading, mark assets finalized only in `finalize_asset`, and expose trusted readiness. |
| `api/src/shared/storage.py` | Modify | Optionally add object-exists/HEAD helper for finalize or resolver validation. |
| `api/src/features/generation/models.py` | Modify | Add `SelectedAssetSummary` and `selected_assets`; keep `selected_asset_ids` canonical. |
| `api/src/features/generation/planner.py` | Modify | Send normalized selected summaries and deterministic role rules to the planner. |
| `api/src/features/generation/orchestrator.py` | Modify | Add pre/post planner normalization, trusted readiness checks, ambiguity guards, and atomic-flow allowlist. |
| `view/src/features/chat/domain/dto.ts` | Modify | Add frontend `SelectedAssetSummary` DTO. |
| `view/src/features/chat/application/build-generate-request.ts` | Modify | Emit deduped IDs plus summaries filtered to selected IDs. |
| `view/src/app/page.tsx` | Modify | Build summaries from current `sessionAssets`; include `selectedWorkflow` and `useTurbo` dependencies. |
| `api/src/tests/test_orchestrator_agent.py` | Modify | Cover trusted readiness, unselected planner roles, ambiguity, and unsupported future workflows. |
| `view/src/features/chat/application/__tests__/build-generate-request.test.ts` | Modify | Cover DTO normalization and stale dependency regression inputs. |

## Interfaces / Contracts

```ts
interface SelectedAssetSummary { id: string; name?: string; status?: string; media_type?: "image" | "file"; description?: string; tags?: string[]; }
```

Normalization rules: duplicate IDs are deduped; summaries whose IDs are absent from `selected_asset_ids` are ignored or rejected before planning; missing summaries are legacy-safe but may force clarification; stale client status never overrides backend readiness.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Backend unit | Pending/failed/deleted/unreadable assets block from trusted backend state. | Asset service/orchestrator tests with fake storage HEAD. |
| Backend unit | Planner returns unselected assets or summary-only IDs. | Fake planner decisions must produce `missing_asset`/blocked response. |
| Backend unit | Multiple identity/extraction candidates and composition without role intent. | Ensure clarification even with high confidence. |
| Frontend unit | DTO emits canonical IDs, filters summaries, dedupes IDs, preserves legacy behavior. | Builder tests. |
| Regression | `selectedWorkflow`/`useTurbo` changes affect submitted orchestration request. | Existing page-level or extracted handler test. |

## Migration / Rollout

Add nullable readiness columns with safe defaults for existing active assets, then backfill as `finalized` only when already known readable or verified via storage HEAD. Deploy backend compatibility first, then frontend summaries.

## Open Questions

None.
