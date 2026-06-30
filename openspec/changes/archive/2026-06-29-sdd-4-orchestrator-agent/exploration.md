## Exploration: SDD 4 Orchestrator Agent

### Current State
The backend already has the execution primitives, but not the intelligent router. `GenerationService` resolves a declared `workflow_name` into a ComfyUI manifest/template, validates whitelisted models, injects typed params, and spawns the right Modal task (`T4`, `L4`, or `A100`). Asset-backed inputs are already supported through `ImageArtifact.asset_id` plus the `resolve_asset_url` callback wired in `api/app.py`, so the missing piece is deciding *which* typed flow to run from free text and selected assets.

### Affected Areas
- `api/src/features/generation/router.py` — current generation entrypoint; needs an orchestration route or request shape extension.
- `api/src/features/generation/service.py` — existing flow dispatch logic; best place to add routing/planning orchestration.
- `api/src/shared/workflows/engine.py` — already parameterizes templates; should remain the executor, not the planner.
- `api/src/shared/flows/{extraction,composition,identity}.py` — typed contracts the orchestrator must target.
- `api/src/features/generation/modal_tasks.py` — final execution path; no LLM logic should leak here.
- `api/app.py` — wires the asset resolver; orchestration must reuse this for asset ID injection.
- `view/src/features/chat/domain/dto.ts` and `view/src/features/chat/application/build-generate-request.ts` — current client contract still assumes explicit workflow selection and includes stale `identidad_gguf`.

### Approaches
1. **Structured LLM Planner + Typed Executor** — LLM returns a strict JSON decision (`workflow_name`, asset role mapping, params, confidence), backend validates it, injects asset IDs via the existing resolver, then calls the current typed dispatch path.
   - Pros: Reuses current engine/Modal flow, easiest to validate/test, keeps raw LLM output away from ComfyUI internals.
   - Cons: Needs prompt/schema design and a fallback when the model is unavailable or low-confidence.
   - Effort: Medium

2. **Heuristic Router with LLM Fallback** — rules/patterns handle obvious cases (extract, compose, edit), and the LLM only resolves ambiguous or mixed-intent prompts.
   - Pros: Cheaper, faster for common requests, less dependency on model behavior.
   - Cons: More branching logic to maintain, weaker coverage for long-tail requests, less aligned with the “LLM brain” goal.
   - Effort: Medium

### Recommendation
Use **Structured LLM Planner + Typed Executor**. The existing system already has the right seam: keep ComfyUI JSON resolution in `WorkflowEngine`, let the orchestrator choose among `extraction`, `composition`, and `identity` (or `flux2_editing` where appropriate), and inject asset IDs through the existing resolver before spawning Modal. That gives the LLM decision power without turning it into a graph generator.

### Risks
- Prompt injection or malformed LLM output could route to the wrong flow unless the response is strictly schema-validated.
- Asset ownership must stay enforced through `resolve_asset_url`; never trust client-provided paths.
- The client contract is stale (`identidad_gguf` still exists in the frontend DTOs while the backend rejects it), so the orchestrator change will need contract cleanup.

### Ready for Proposal
Yes — tell the user we should decide whether SDD 4 adds a new orchestration endpoint or extends `/generate` backward-compatibly before implementation.
