# Design: SDD 4 Orchestrator Agent

## Technical Approach

Add a prompt-first orchestration layer in front of the existing typed generation paths. The LLM planner produces only a strict JSON plan; backend Pydantic models validate it, map selected `asset_id`s to typed `ImageArtifact` roles, and dispatch through the current `GenerationService.dispatch_flow()` or `enqueue_modal_work()` paths. `WorkflowEngine` and Modal tasks remain graph executors, not planners.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Entrypoint | Add `POST /generate/orchestrate` | Extend `/generate` | Keeps legacy typed Flux 2 contract stable and gives frontend a clear prompt-first outcome union. |
| Planner boundary | New service-owned structured planner module | LLM-generated ComfyUI graph | Existing safety model depends on allowlisted workflows, manifests, cached models, and typed flow contracts. |
| Asset handling | Planner maps roles to selected asset ids; service builds `ImageArtifact(volume_path="input/{asset_id}", asset_id=...)` | Trust client URLs/paths | Current resolver in `api/app.py` enforces session ownership; fail-closed behavior already exists. |
| Stage visibility | Return initial stage list in HTTP outcome, then reuse WebSocket for generation | Add new WebSocket channel | Planning/validation are synchronous; execution progress already has a working WS lifecycle. |

## Data Flow

```text
Chat prompt + selected assets
  -> POST /generate/orchestrate
  -> OrchestratorPlanner.plan()
  -> validate workflow/params/assets/confidence
      | low confidence -> clarification_required
      | missing role    -> missing_asset
      | valid plan      -> typed Flow / Flux request
  -> GenerationService.dispatch_flow()/enqueue_modal_work()
  -> WorkflowEngine -> Modal task -> existing WS/image endpoints
```

## File Changes

| File | Action | Description |
|---|---|---|
| `api/src/features/generation/models.py` | Modify | Add `OrchestrateRequest`, `PlannerDecision`, `OrchestrateResponse`, stage/outcome models, and planner error codes. |
| `api/src/features/generation/planner.py` | Create | LLM adapter and strict JSON schema prompt. Reads provider/model from env; exposes injectable planner for tests. |
| `api/src/features/generation/orchestrator.py` | Create | Validates planner output against allowlist, builds typed flow requests, handles clarification/missing-asset outcomes. |
| `api/src/features/generation/service.py` | Modify | Add `orchestrate(...)` method that calls planner/orchestrator and reuses current dispatch functions. |
| `api/src/features/generation/router.py` | Modify | Add `/generate/orchestrate`, preserve `_validate_session`, `_handle_service_errors`, and `_resolve_asset_url_cb` wiring. |
| `api/app.py` | Modify | Wire planner dependency/config if needed; keep asset resolver lifecycle unchanged. |
| `view/src/features/chat/domain/dto.ts` | Modify | Replace stale `identidad_gguf` default path with orchestration request/outcome types. |
| `view/src/features/chat/application/build-generate-request.ts` | Modify | Convert to `buildOrchestrateRequest(prompt, selectedAssets)` for default UX. |
| `view/src/shared/infrastructure/api-client.ts` | Modify | Add `submitOrchestrate()` calling `/generate/orchestrate` and normalize outcome union. |
| `view/src/features/chat/presentation/components/*` | Modify | Hide default workflow controls, show selected asset context and stage timeline. |
| `api/src/tests/test_orchestrator_agent.py` | Create | Unit/integration tests for planner validation, clarification, missing assets, and dispatch safety. |
| `view/src/features/chat/**/__tests__/*` | Modify/Create | Contract and UI-state tests for orchestration outcomes and stale-field removal. |

## Interfaces / Contracts

```python
PlannerWorkflow = Literal["extraction", "composition", "identity", "flux2_editing", "flux2_txt2img"]
OrchestrateOutcome = Literal["job_started", "clarification_required", "missing_asset", "error"]

class OrchestrateRequest(BaseModel):
    prompt: str
    selected_asset_ids: list[str] = []
    workspace_context: dict[str, str] | None = None

class PlannerDecision(BaseModel):
    workflow_name: PlannerWorkflow
    asset_roles: dict[str, str]
    params: dict[str, Any]
    confidence: float
    clarification: str | None = None
    missing_assets: list[str] = []
```

Response is one of: job `{outcome:"job_started", job_id, status:"pending", stages}`, clarification `{outcome:"clarification_required", question, stages}`, missing asset `{outcome:"missing_asset", missing_roles, guidance, stages}`, or typed error.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | JSON schema rejection, confidence threshold, allowlist/param filtering, role mapping | Mock planner and resolver; assert no Modal spawn on blocked outcomes. |
| Integration | `/generate/orchestrate` returns 202 job or 200 blocked outcome; session ownership preserved | FastAPI `LazyTestClient`, patched Modal tasks, fake `resolve_asset_url`. |
| Frontend | Request builder omits `workflow_name`/`identidad_gguf`; outcome reducer renders stages | Existing TS unit scripts plus component tests where available. |
| E2E | Prompt submits, stage chain appears, WS continues after job start | Existing frontend flow with mocked API/WebSocket. |

## Migration / Rollout

No data migration required. Roll out by adding `/generate/orchestrate` and switching the default chat path to it; keep existing `/generate`, `/generate/extraction`, `/generate/composition`, and `/generate/identity` endpoints as rollback paths.

## Open Questions

- [ ] Which LLM provider/model and env variable names should the planner use in production?
- [ ] Should advanced manual workflow controls remain behind a feature flag or be removed from the default sidebar entirely?
