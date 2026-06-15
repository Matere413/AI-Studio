# Tasks: Realistic Persona Workflow

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~560 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Workflow files + manifest schema + engine defaults + whitelist | PR 1 | base: main; tests included |
| 2 | API models + service + router dispatch | PR 2 | base: main after PR 1; tests included |
| 3 | Frontend types + store + PromptPanel controls | PR 3 | base: main after PR 2; tests included |

## Phase 1: Workflow Backbone

- [x] 1.1 RED: Write test for manifest schema with prompt-template/persona-metadata fields in `test_workflow_models.py`
- [x] 1.2 GREEN: Add defaults, prompt-templates, persona-metadata to `ManifestSchema` in `api/src/shared/workflows/models.py`
- [x] 1.3 RED: Write test for engine applying manifest defaults generically in `test_workflow_engine.py`
- [x] 1.4 GREEN: Apply manifest defaults before runtime params; resolve prompt templates in `api/src/shared/workflows/engine.py`
- [x] 1.5 Create `api/src/workflows/realistic_persona/workflow.json` with CheckpointLoaderSimple/CLIP/KSampler/VAE/SaveImage graph
- [x] 1.6 Create `api/src/workflows/realistic_persona/manifest.yaml` with controls, defaults, output types, prompt-templates
- [x] 1.7 Add `moodyRealMix_zitV7.safetensors` to whitelist in `api/src/shared/modal_config.py`

## Phase 2: API Layer

- [x] 2.1 RED: Write test for persona field validation on `GenerateRequest` in `test_generation_models.py`
- [x] 2.2 GREEN: Extend `WorkflowName` with `realistic_persona`; add `age`/`gender`/`ethnicity`/`wardrobe`/`expression`/`background`/`output_type` in `api/src/features/generation/models.py`
- [x] 2.3 RED: Write test for service locking checkpoint on persona workflow in `test_generation_service.py`
- [x] 2.4 GREEN: Pass persona params to engine; ignore checkpoint/Lora overrides for locked workflow in `api/src/features/generation/service.py`
- [x] 2.5 Forward persona fields in `api/src/features/generation/router.py`
- [x] 2.6 REFACTOR: Consolidate API-layer test coverage

## Phase 3: Frontend Controls

- [x] 3.1 RED: Write test for persona types and payload shape in `client.test.ts`
- [x] 3.2 GREEN: Add `realistic_persona` + persona type fields in `view/src/features/generation/api/types.ts`
- [x] 3.3 Include persona fields in `/api/generate` payload in `view/src/features/generation/api/client.ts`
- [x] 3.4 RED: Write test for store validation of persona workflow in `generationStore.test.ts`
- [x] 3.5 GREEN: Validate `realistic_persona`, age range, cleanup non-persona fields in `view/src/features/generation/stores/generationStore.ts`
- [x] 3.6 Add persona controls (age slider, gender/ethnicity/wardrobe/expression/background selects, output_type radio) in `view/src/features/generation/components/PromptPanel.tsx`
- [x] 3.7 Hide checkpoint/Lora/technical controls when persona workflow selected in `PromptPanel.tsx`

## Phase 4: Integration Verification

- [x] 4.1 Verify e2e: `POST /generate` with `workflow=realistic_persona` + full controls returns 202
- [x] 4.2 Verify e2e: `POST /generate` with undeclared fields returns 422
- [x] 4.3 Verify e2e: persona workflow UI submission calls `/api/generate` with correct payload shape
- [x] 4.4 Run full test suite: `python3 -m pytest` (api) and `vitest run` (view)
