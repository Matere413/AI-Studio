# Apply Progress: Persona Identity Preservation

## Current Batch

- **PR slice**: PR 3 — Frontend UI Layer
- **Delivery strategy**: chained-pr / auto-chain
- **Chain strategy**: feature-branch-chain
- **Tracker branch**: `feature/persona-identity-preservation`
- **Previous implementation branch**: `feature/persona-identity-preservation-pr2-backend-api`
- **Implementation branch**: `feature/persona-identity-preservation-pr3-frontend-ui`
- **Mode**: Strict TDD (`npm run test` in `view/`, Vitest)

## Completed Tasks

- [x] 1.1 `modal_config.py`: added RealVisXL_V4.0, FaceID adapter, and CLIP Vision to the default whitelist; added `ComfyUI_IPAdapter_plus` to ComfyUI image run commands.
- [x] 1.2 `manifest.yaml`: changed default checkpoint to `RealVisXL_V4.0.safetensors`; added `image_url` and `faceid_strength` inputs/defaults; removed `IPAdapter` from `v1_excluded_nodes`.
- [x] 1.3 `workflow.json`: added `LoadImageFromBase64`, `IPAdapterModelLoader`, `CLIPVisionLoader`, and `IPAdapterFaceIDPlusV2`; rewired KSampler model input to the IP-Adapter output.
- [x] 1.4 Verify: workflow resolves with `faceid_strength=0` and `faceid_strength=0.75`.
- [x] 2.1 `models.py`: added `image_url: Optional[str]` on `GenerateRequest` with http(s)/data URI validation.
- [x] 2.2 `service.py`: passes persona `image_url` into workflow params and sets `faceid_strength=0.75` when present, `0` when absent.
- [x] 2.3 `router.py`: forwards `request.image_url` to `enqueue_modal_work`.
- [x] 2.4 Test: parameterized `GenerateRequest` validation for http URL, data URI, invalid values, and `None`.
- [x] 2.5 Test: `enqueue_modal_work` resolves persona graph with correct `image_url` and FaceID strength with/without a reference image.
- [x] 2.6 Test: `POST /generate` accepts `image_url`, returns 202, and produces a graph with enabled FaceID strength.
- [x] 3.1 `types.ts`: added `image_url?: string` to frontend `GenerationParameters`.
- [x] 3.2 `generationStore.ts`: added `referenceFaceUrl`, `setReferenceFaceUrl`, and `clearReferenceFace`; persona normalization preserves `image_url` and removes it when leaving persona workflows.
- [x] 3.3 `client.ts`: includes `image_url` in `/api/generate` payloads when present.
- [x] 3.4 `useGenerationFlow.ts`: reads stored `referenceFaceUrl` and sends it as `image_url` only for `realistic_persona` generations.
- [x] 3.5 `PromptPanel.tsx`: added optional persona-only PNG/JPEG upload, 10MB validation, data URI conversion, progress text, preview, and remove button.
- [x] 3.6 Test: covered `setReferenceFaceUrl`, `clearReferenceFace`, reset clearing, and store default reference state.
- [x] 3.7 Test: covered persona `image_url` normalization and removal when switching away from persona.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `api/src/tests/test_modal_config.py` | Unit | ✅ 17/17 existing relevant tests passed before edits | ✅ Tests required missing `comfyui_run_commands`, RealVisXL, FaceID, and CLIP Vision whitelist entries | ✅ `21 passed`; final related suite `76 passed` | ✅ 3 behaviors: checkpoint whitelist, identity model whitelist, custom node install command | ✅ Extracted `comfyui_run_commands` tuple and reused it in image setup |
| 1.2 | `api/src/tests/test_workflow_templates.py` | Unit | ✅ 17/17 existing relevant tests passed before edits | ✅ Manifest assertions expected RealVisXL defaults and identity inputs before implementation | ✅ `21 passed`; final related suite `76 passed` | ✅ Multiple manifest paths: defaults, input mappings, excluded-node metadata | ➖ None needed |
| 1.3 | `api/src/tests/test_workflow_templates.py` | Unit | ✅ 17/17 existing relevant tests passed before edits | ✅ Workflow assertions expected identity nodes and KSampler rewiring before implementation | ✅ `21 passed`; final related suite `76 passed` | ✅ Multiple graph paths: loader nodes, adapter model, CLIP Vision model, sampler model edge | ➖ None needed |
| 1.4 | `api/src/tests/test_workflow_templates.py` | Unit | ✅ 17/17 existing relevant tests passed before edits | ✅ Parameterized resolution test expected prompt-only and identity-conditioned inputs before graph/manifest implementation | ✅ `21 passed`; final related suite `76 passed` | ✅ 2 cases: `faceid_strength=0` with empty image and `faceid_strength=0.75` with data URI | ➖ None needed |
| 2.1 | `api/src/tests/test_generation_models.py` | Unit | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ `image_url` tests failed as extra forbidden before model field existed | ✅ `108 passed`; refactor rerun `108 passed` | ✅ 7 cases: http URL, https URL, data URI, `None`, and 3 invalid formats | ✅ Extracted `is_supported_reference_image_url()` pure helper |
| 2.2 | `api/src/tests/test_generation_service.py` | Unit/Integration | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ FaceID strength test failed with `0 == 0.75` before service mapped the flag | ✅ `108 passed`; refactor rerun `108 passed` | ✅ 2 paths: prompt-only reference fallback (`image_url=""`, strength `0`) and reference image enabled (`0.75`) | ➖ None needed |
| 2.3 | `api/src/tests/test_generation_router.py` | Integration | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ `POST /generate` with `image_url` returned 422 before router/model accepted and forwarded the field | ✅ `108 passed`; refactor rerun `108 passed` | ✅ API request verifies 202 response and resolved graph receives image + strength | ➖ None needed |
| 2.4 | `api/src/tests/test_generation_models.py` | Unit | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ Parameterized validation failed on extra-forbidden `image_url` before implementation | ✅ `108 passed`; refactor rerun `108 passed` | ✅ Accepted and rejected format sets cover all task cases | ✅ Shared helper keeps validation readable |
| 2.5 | `api/src/tests/test_generation_service.py` | Unit/Integration | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ Persona graph did not enable FaceID strength for non-empty `image_url` before service implementation | ✅ `108 passed`; refactor rerun `108 passed` | ✅ With/without image branches asserted against resolved graph nodes 10 and 12 | ➖ None needed |
| 2.6 | `api/src/tests/test_generation_router.py` | Integration | ✅ `98 passed` across relevant backend safety net before PR 2 edits | ✅ API returned 422 before `GenerateRequest` accepted `image_url` | ✅ `108 passed`; refactor rerun `108 passed` | ✅ 202 response plus Modal spawn graph assertions prove dispatch path | ➖ None needed |
| 3.1 | `view/src/features/generation/api/client.test.ts`, `view/src/features/generation/stores/generationStore.test.ts`, `view/src/features/generation/hooks/useGenerationFlow.test.tsx`, `view/src/features/generation/components/PromptPanel.test.tsx` | Unit/Integration | ⚠️ `npm run test -- ...` initially failed because `view/package.json` had no `test` script; Vitest safety net via `npm exec vitest run -- ...` produced 64 passing existing tests and 11 RED failures after test additions | ✅ Tests referenced `image_url` before frontend type/payload support was implemented | ✅ `npm run test -- ...` → 75 passed | ✅ Data URI and persona/non-persona cases exercise typed payload behavior | ✅ Added `test: vitest run` script so required frontend command works |
| 3.2 | `view/src/features/generation/stores/generationStore.test.ts` | Unit | ⚠️ Same PR 3 safety net note: missing `npm run test` script before edits; existing store tests passed under Vitest before production code changes | ✅ Store action tests failed with `setReferenceFaceUrl is not a function`; normalization test retained `image_url` outside persona before implementation | ✅ `npm run test -- ...` → 75 passed | ✅ Covers set, clear, reset, persona preserve, and non-persona removal paths | ➖ None needed |
| 3.3 | `view/src/features/generation/api/client.test.ts` | Unit | ⚠️ Same PR 3 safety net note; existing client tests passed under Vitest before production code changes | ✅ Payload test failed because `image_url` was absent from submitted body | ✅ `npm run test -- ...` → 75 passed | ✅ Existing prompt-only/persona-control payload tests plus new image payload case prove optional behavior | ➖ None needed |
| 3.4 | `view/src/features/generation/hooks/useGenerationFlow.test.tsx` | Integration | ⚠️ Same PR 3 safety net note; existing hook tests passed under Vitest before production code changes | ✅ Hook test failed because stored `referenceFaceUrl` was not merged into persona submissions | ✅ `npm run test -- ...` → 75 passed | ✅ Covers persona submission includes `image_url` and non-persona submission omits it | ➖ None needed |
| 3.5 | `view/src/features/generation/components/PromptPanel.test.tsx` | Integration | ⚠️ Same PR 3 safety net note; existing PromptPanel tests passed under Vitest before production code changes | ✅ UI tests failed because upload control, preview, validation errors, remove button, and referenced submit payload did not exist | ✅ `npm run test -- ...` → 75 passed | ✅ Covers visible control, valid PNG conversion, invalid format, oversize file, remove, and submit with stored reference | ✅ Used `ChangeEvent` type import to keep component typing explicit |
| 3.6 | `view/src/features/generation/stores/generationStore.test.ts` | Unit | ⚠️ Same PR 3 safety net note | ✅ Store action tests failed before actions existed | ✅ `npm run test -- ...` → 75 passed | ✅ Set/clear plus reset clearing cover action behavior | ➖ None needed |
| 3.7 | `view/src/features/generation/stores/generationStore.test.ts` | Unit | ⚠️ Same PR 3 safety net note | ✅ Normalization tests failed before persona-only `image_url` handling was added | ✅ `npm run test -- ...` → 75 passed | ✅ Persona keeps `image_url`; switching to `txt2img` removes it | ➖ None needed |

## Test Summary

- **Safety net**: `python3 -m pytest src/tests/test_modal_config.py src/tests/test_workflow_templates.py` → 17 passed before production edits.
- **RED evidence**: first run after test edits failed on missing `comfyui_run_commands` import, proving tests preceded production code.
- **GREEN command**: `python3 -m pytest src/tests/test_modal_config.py src/tests/test_workflow_templates.py` → 21 passed.
- **Related regression command**: `python3 -m pytest src/tests/test_modal_config.py src/tests/test_workflow_templates.py src/tests/test_generation_service.py src/tests/test_model_cache.py` → 76 passed.
- **Total test cases added/updated for PR 1**: 5 behavioral test functions, including 1 parameterized verification with 2 cases.
- **PR 2 safety net**: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py` → 98 passed before PR 2 production edits.
- **PR 2 RED evidence**: same command after test edits → 7 failed, 101 passed (`image_url` extra forbidden, FaceID strength stayed `0`, API returned `422`).
- **PR 2 GREEN command**: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py` → 108 passed.
- **PR 2 refactor command**: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py` → 108 passed.
- **Total test cases added/updated for PR 2**: 5 behavioral test functions, including 2 parameterized validation tests covering 7 `image_url` cases.
- **PR 3 safety-net command requested**: `npm run test -- src/features/generation/stores/generationStore.test.ts src/features/generation/api/client.test.ts src/features/generation/hooks/useGenerationFlow.test.tsx src/features/generation/components/PromptPanel.test.tsx` initially failed before production edits because `view/package.json` did not expose a `test` script.
- **PR 3 RED evidence**: `npm exec vitest run -- src/features/generation/stores/generationStore.test.ts src/features/generation/api/client.test.ts src/features/generation/hooks/useGenerationFlow.test.tsx src/features/generation/components/PromptPanel.test.tsx` after test edits → 11 failed, 64 passed.
- **PR 3 GREEN command**: `npm run test -- src/features/generation/stores/generationStore.test.ts src/features/generation/api/client.test.ts src/features/generation/hooks/useGenerationFlow.test.tsx src/features/generation/components/PromptPanel.test.tsx` → 75 passed.
- **PR 3 refactor command**: same targeted frontend command → 75 passed.
- **PR 3 full frontend regression**: `npm run test` in `view/` → 126 passed across 12 test files.
- **Total test cases added/updated for PR 3**: 12 behavioral test functions across store, client, hook, and PromptPanel.
- **Layers used**: Unit and Integration.
- **Approval tests**: None — tasks changed behavior rather than refactoring existing behavior.
- **Pure functions created**: 1 (`is_supported_reference_image_url`).

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `api/src/shared/modal_config.py` | Modified | Added identity-preservation model allow-list entries and IP-Adapter Plus custom node install command. |
| `api/src/workflows/realistic_persona/manifest.yaml` | Modified | Added identity inputs/defaults and switched default checkpoint to RealVisXL_V4.0. |
| `api/src/workflows/realistic_persona/workflow.json` | Modified | Added FaceID Plus V2 graph nodes and routed KSampler through the adapter output. |
| `api/src/tests/test_modal_config.py` | Modified | Added PR 1 infrastructure tests. |
| `api/src/tests/test_workflow_templates.py` | Modified | Added PR 1 manifest, graph, and resolution tests. |
| `api/src/tests/test_generation_service.py` | Modified | Updated realistic persona test fixture checkpoint to RealVisXL_V4.0 after the manifest default changed. |
| `openspec/changes/persona-identity-preservation/tasks.md` | Modified | Marked Phase 1 / PR 1 tasks complete. |
| `openspec/changes/persona-identity-preservation/apply-progress.md` | Created | Captured cumulative PR 1 progress and Strict TDD evidence. |
| `api/src/features/generation/models.py` | Modified | Added persona-scoped `image_url` request field and URL/data URI validation helper. |
| `api/src/features/generation/service.py` | Modified | Sends persona reference image params and FaceID strength into workflow resolution. |
| `api/src/features/generation/router.py` | Modified | Forwards `request.image_url` to the service layer. |
| `api/src/tests/test_generation_models.py` | Modified | Added parameterized `GenerateRequest.image_url` validation coverage. |
| `api/src/tests/test_generation_service.py` | Modified | Added persona reference-image graph assertions for prompt-only and identity-enabled paths. |
| `api/src/tests/test_generation_router.py` | Modified | Added POST `/generate` coverage for persona reference image requests and updated persona cache fixture. |
| `openspec/changes/persona-identity-preservation/tasks.md` | Modified | Marked Phase 2 / PR 2 tasks complete. |
| `openspec/changes/persona-identity-preservation/apply-progress.md` | Modified | Merged PR 2 progress and Strict TDD evidence without removing PR 1 progress. |
| `view/package.json` | Modified | Added `npm run test` script backed by Vitest for frontend TDD execution. |
| `view/src/features/generation/api/types.ts` | Modified | Added optional `image_url` to frontend generation parameters. |
| `view/src/features/generation/api/client.ts` | Modified | Sends optional `image_url` in generation payloads. |
| `view/src/features/generation/stores/generationStore.ts` | Modified | Added reference-face state/actions and persona-only `image_url` normalization. |
| `view/src/features/generation/hooks/useGenerationFlow.ts` | Modified | Merges stored reference face URL into persona submissions only. |
| `view/src/features/generation/components/PromptPanel.tsx` | Modified | Added optional persona reference-face upload with validation, data URI conversion, preview, progress text, and removal. |
| `view/src/features/generation/components/PromptPanel.module.css` | Modified | Added helper text and reference preview styles. |
| `view/src/features/generation/api/client.test.ts` | Modified | Added payload coverage for persona `image_url`. |
| `view/src/features/generation/stores/generationStore.test.ts` | Modified | Added reference-face actions and normalization coverage. |
| `view/src/features/generation/hooks/useGenerationFlow.test.tsx` | Modified | Added persona/non-persona reference-face submission coverage. |
| `view/src/features/generation/components/PromptPanel.test.tsx` | Modified | Added upload visibility, validation, preview, removal, and submit coverage. |
| `openspec/changes/persona-identity-preservation/tasks.md` | Modified | Marked Phase 3 / PR 3 tasks complete. |
| `openspec/changes/persona-identity-preservation/apply-progress.md` | Modified | Merged PR 3 frontend progress and Strict TDD evidence without removing PR 1 or PR 2 progress. |

## Deviations from Design

None — implementation follows the PR 1, PR 2, and PR 3 design scope.

## Issues Found

- The exact runtime availability of `LoadImageFromBase64` remains an upstream Modal/ComfyUI custom-node compatibility concern already listed as an open question in `design.md`.
- `view/package.json` did not expose the requested `npm run test` command before PR 3; PR 3 adds the Vitest script so the strict frontend TDD command now works.

## Remaining Tasks

- [x] Phase 3 / PR 3: Frontend UI
- [ ] Verification phase: run final SDD verify for the full chained change.

## Workload / PR Boundary

- **Mode**: chained PR slice
- **Current work unit**: Frontend UI Layer
- **Boundary**: starts from PR 2 branch `feature/persona-identity-preservation-pr2-backend-api`; ends with the frontend storing optional reference faces, validating uploads, and sending persona `image_url` payloads. Verification/archive remain deferred.
- **Estimated review budget impact**: focused PR 3 frontend/test slice; cumulative working tree includes prior PR 1 and PR 2 changes because this is a feature-branch-chain child branch.
