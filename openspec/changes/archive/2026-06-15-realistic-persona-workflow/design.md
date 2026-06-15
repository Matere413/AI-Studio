# Design: Realistic Persona Workflow

## Technical Approach

Add a dedicated `realistic_persona` workflow beside existing ComfyUI workflow assets, then expose it through the current FastAPI `GenerateRequest` → router → `GenerationService` → `WorkflowEngine` path and the feature-first frontend generation UI. The workflow will follow the `product_premium` isolation pattern, but with persona-owned controls and a manifest-driven prompt composition contract so controls are validated, defaulted, and resolved without hardcoded node IDs. V1 uses `moodyRealMix_zitV7.safetensors`, excludes identity-preservation nodes, and relies on seed plus prompt consistency only.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Workflow boundary | Create `api/src/workflows/realistic_persona/` with `workflow.json` and `manifest.yaml` | Reuse `txt2img`; extend `product_premium` | Existing architecture separates semantic workflows. Persona output needs its own checkpoint, controls, negative prompt, and future identity-extension space. |
| Parameter resolution | Extend manifest schema with generic defaults and prompt-template metadata, applied by `WorkflowEngine` | Compose persona prompts in router/service; map all controls directly to one CLIP field | Service/router composition would hardcode workflow semantics. Direct node mapping cannot safely map multiple controls to the same text field because later values overwrite earlier ones. |
| Model handling | Lock manifest default checkpoint to `moodyRealMix_zitV7.safetensors` and validate through existing whitelist/cache flow | Allow user checkpoint override | Stable persona API should not expose model selectors in V1, and the checkpoint is a workflow contract dependency. |
| Frontend controls | Add workflow-specific presentational controls in `PromptPanel` and typed state fields | Generic dynamic form renderer | Current UI uses explicit workflow branches (`product_premium`), so a focused branch is smaller and testable. |

## Data Flow

    PromptPanel controls
        → generationStore validates typed params
        → submitGenerate sends workflow + persona fields
        → GenerateRequest validates enum/ranges/extra fields
        → GenerationService builds params and loads WorkflowEngine
        → WorkflowEngine applies manifest defaults/templates
        → cache validates moodyRealMix_zitV7.safetensors
        → run_generation.spawn(resolved ComfyUI graph)

## File Changes

| File | Action | Description |
|---|---|---|
| `api/src/workflows/realistic_persona/workflow.json` | Create | API-format ComfyUI graph using `CheckpointLoaderSimple`, `EmptyLatentImage`, positive/negative `CLIPTextEncode`, `KSampler`, `VAEDecode`, `SaveImage`; no FaceDetailer/IPAdapter/InstantID nodes. |
| `api/src/workflows/realistic_persona/manifest.yaml` | Create | Declares checkpoint, persona controls, output-type defaults/dimensions, negative prompt, and prompt-template metadata. |
| `api/src/shared/workflows/models.py` | Modify | Add manifest fields for defaults, prompt templates, and persona/output-type metadata while preserving `extra="forbid"`. |
| `api/src/shared/workflows/engine.py` | Modify | Apply manifest defaults before runtime params and resolve prompt templates generically. Keep node/field validation and whitelist validation. |
| `api/src/features/generation/models.py` | Modify | Extend `WorkflowName`; add `age`, `gender`, `ethnicity`, `wardrobe`, `expression`, `background`, `output_type`; enforce persona-only scope and age range. |
| `api/src/features/generation/service.py` | Modify | Pass persona params to the engine, ignore checkpoint/Lora overrides for locked persona workflow, and reuse graph model extraction for cache checks. |
| `api/src/features/generation/router.py` | Modify | Forward typed persona fields to `GenerationService.enqueue_modal_work`. |
| `api/src/shared/modal_config.py` | Modify | Add `moodyRealMix_zitV7.safetensors` to the default checkpoint whitelist. |
| `api/src/tests/test_*` | Modify | Add model, router, service, workflow engine, and template coverage for the new contract. |
| `view/src/features/generation/api/types.ts` | Modify | Add workflow name and persona parameter types. |
| `view/src/features/generation/api/client.ts` | Modify | Include persona fields in `/api/generate` payload. |
| `view/src/features/generation/stores/generationStore.ts` | Modify | Validate `realistic_persona`, age range, and cleanup of non-persona fields. |
| `view/src/features/generation/components/PromptPanel.tsx` | Modify | Add persona controls and hide checkpoint/Lora/technical controls for persona workflow. |
| `view/src/features/generation/**/*.test.ts*` | Modify | Cover UI selection, payload, validation, and store normalization. |

## Interfaces / Contracts

API request additions are optional except where UI chooses to send them: `workflow|workflow_name = "realistic_persona"`, `age: int 18..100`, `gender`, `ethnicity`, `wardrobe`, `expression`, `background`, `output_type: "portrait" | "full-body" | "lifestyle" | "editorial"`. Extra fields remain forbidden. Manifest-owned defaults fill omitted controls.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Pydantic persona validation and manifest schema/template resolution | Add failing tests in `test_generation_models.py`, `test_workflow_models.py`, `test_workflow_engine.py`. |
| Integration | Router/service acceptance, whitelist rejection, cache miss, no checkpoint override | Extend `test_generation_router.py` and `test_generation_service.py` with patched cache/spawn. |
| Frontend | Workflow option, controls, no model selectors, payload shape | Extend existing Vitest tests for store, client, and `PromptPanel`. |
| Manual | ComfyUI node/model compatibility and natural aesthetic | Required because `state/inventory.json` is unavailable. |

## Migration / Rollout

No data migration required. Roll out by adding the workflow files and API/UI option behind the stable name `realistic_persona`; rollback removes that workflow and whitelist entry.

## Open Questions

- None blocking. Manual ComfyUI validation remains required because node inventory validation is unavailable.
