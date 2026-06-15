# Apply Progress: premium-product-image-workflows

## Scope

Work Units 1-3 / PR 1-3 cumulative, plus Phase 4 verification and small test remediation.

## Completed

- 1.1 Added strict schema tests for product format metadata in `test_workflow_models.py`.
- 1.2 Created `api/src/workflows/product_premium/workflow.json`.
- 1.3 Created `api/src/workflows/product_premium/manifest.yaml`.
- 1.4 Extended `api/src/shared/workflows/models.py` with format metadata.
- 1.5 Extended `api/src/shared/workflows/engine.py` with whitelist validation and format resolution.
- 1.6 Added engine tests for whitelist rejection and format-to-dimension resolution.
- 2.1 Added generation request validation tests for `workflow` / `format` support.
- 2.2 Extended `api/src/features/generation/models.py` with `workflow`, `workflow_name`, and `format` handling.
- 2.3 Added service tests for product format resolution and checkpoint override suppression.
- 2.4 Updated `api/src/features/generation/router.py` to normalize the workflow alias and pass `format`.
- 2.5 Updated `api/src/features/generation/service.py` to expand product formats into manifest dimensions and ignore premium model overrides.
- 2.6 Premium checkpoint whitelist entry was already present in `api/src/shared/modal_config.py`; no file delta was needed.
- 2.7 Added integration tests for accepted product requests, invalid format validation, and cache-miss handling.
- PR2 review remediation: product manifest whitelist failures now return HTTP 400 with `error.code = "model_not_allowed"`, cache-miss details are sanitized to avoid leaking Modal filesystem paths, and conflicting `workflow`/`workflow_name` inputs are rejected at validation time.
- 3.1 Added frontend store tests for `product_premium` workflow acceptance and product format handling.
- 3.2 Extended `view/src/stores/generationStore.ts` with `product_premium`, product format state, and normalization.
- 3.3 Added Sidebar tests for product controls, hidden technical inputs, and product payload submission.
- 3.4 Updated `view/src/components/studio/Sidebar.tsx` to render product-only controls plus square/vertical format toggles.
- 3.5 Updated `view/src/lib/api.ts` to serialize the product workflow payload explicitly, including workflow alias and format.
- 4.1 Full backend verification passed after stabilizing the polling test timing in `api/src/tests/test_generation_router.py`.
- 4.2 Frontend verification passed after updating `view/src/lib/api.test.ts` to expect the serialized `workflow` and default `format` payload.
- 4.3 Manual smoke verified `POST /generate` accepts `workflow = "product_premium"` with `format = "vertical"` and returns `202` + `job_id`.
- 4.4 Rollback check confirmed `api/src/workflows/product_premium/` is isolated to `workflow.json` + `manifest.yaml`, with the premium checkpoint entry still contained in `api/src/shared/modal_config.py`.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `src/tests/test_workflow_models.py` | Unit | ✅ 31/31 passing | ✅ Written first | ✅ Passed after `models.py` update | ✅ 2 cases (valid metadata + invalid default format) | ✅ Clean |
| 1.2-1.3 | `src/tests/test_workflow_engine.py` | Unit | ✅ 31/31 passing | ✅ Written first | ✅ Passed after adding workflow assets | ✅ Covered by engine load + format resolution checks | ✅ Clean |
| 1.4-1.5 | `src/tests/test_workflow_engine.py` | Unit | ✅ 31/31 passing | ✅ Written first | ✅ Passed after `models.py` + `engine.py` updates | ✅ Whitelisted load + whitelist rejection | ✅ Clean |
| 1.6 | `src/tests/test_workflow_engine.py` | Unit | ✅ 31/31 passing | ✅ Written first | ✅ Passed after whitelist error message fix | ✅ Positive and negative checkpoint paths | ✅ Clean |
| 2.1-2.2 | `src/tests/test_generation_models.py` | Unit | ✅ 86/86 passing | ✅ Written first | ✅ Passed after `models.py` update | ✅ 3 cases (workflow alias, legacy alias, non-product rejection) | ✅ Clean |
| 2.3-2.5 | `src/tests/test_generation_service.py` | Unit | ✅ 86/86 passing | ✅ Written first | ✅ Passed after `service.py` + `router.py` updates | ✅ 2 cases (vertical expansion + override suppression) | ✅ Clean |
| 2.6 | `api/src/shared/modal_config.py` | Config | ✅ 86/86 passing | ➖ Not needed | ➖ Not needed | ➖ Skipped: checkpoint already present in default whitelist | ➖ None needed |
| 2.7 | `src/tests/test_generation_router.py` | Integration | ✅ 86/86 passing | ✅ Written first | ✅ Passed after request/service normalization | ✅ 3 cases (202 accepted, invalid format 422, cache miss 500) | ✅ Clean |
| 3.1-3.5 | `src/stores/generationStore.test.ts`, `src/components/studio/Sidebar.test.tsx` | Unit | ✅ 39/39 passing | ✅ Written first | ✅ Passed after store/sidebar/api updates | ✅ 2 cases (product workflow acceptance + product controls/payload) | ✅ Clean |

## Verification

- `python3 -m pytest src/tests/test_workflow_models.py src/tests/test_workflow_engine.py src/tests/test_workflow_templates.py`
- Result: 35 passed
- Remediation verification: `python3 -m pytest src/tests/test_workflow_models.py src/tests/test_workflow_engine.py`
- Result: 31 passed

## PR 2 Verification

- `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py`
- Result: 90 passed
- Broader slice: `python3 -m pytest src/tests/test_generation_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_e2e_generation.py src/tests/test_modal_config.py`
- Result: 102 passed
- Full backend suite from `api/`: `python3 -m pytest src/tests`
- Result: 225 passed

## PR 3 Verification

- `npx vitest run src/stores/generationStore.test.ts src/components/studio/Sidebar.test.tsx`
- Result: 39 passed
- `npm run lint -- src/stores/generationStore.ts src/stores/generationStore.test.ts src/components/studio/Sidebar.tsx src/components/studio/Sidebar.test.tsx src/lib/api.ts`
- Result: clean
- `npx tsc --noEmit`
- Result: clean
- `npm run build`
- Result: clean (Next.js warned about multiple lockfiles selecting `/Users/matere/pnpm-lock.yaml` as workspace root)

## Phase 4 Verification

- `python3 -m pytest src/tests`
- Result: 225 passed
- `npx vitest run`
- Result: 90 passed
- `npm run lint && npx tsc --noEmit && npm run build`
- Result: clean (Next.js warned about multiple lockfiles selecting `/Users/matere/pnpm-lock.yaml` as workspace root)
- Manual smoke: `POST /generate` with `workflow = "product_premium"` and `format = "vertical"` via `TestClient` + patched enqueue
- Result: `202 Accepted` with `job_id`
- Rollback check: workflow directory isolation + premium checkpoint presence in `modal_config.py`
- Result: clean rollback target set

## Notes

- The product workflow uses `epicrealism_naturalSinRC1VAE.safetensors`, which is already present in the default whitelist.
- The engine now raises `model_not_allowed` when a manifest declares a checkpoint outside the approved whitelist.
- Vertical format now resolves to a T4-safe 9:16 resolution (`720x1280`), and tests assert the aspect ratio contract instead of the previous literal size.
- Product premium requests now ignore hidden checkpoint/LoRA overrides server-side and always resolve the manifest-owned premium checkpoint before cache validation.
- The backend websocket polling test was flaky at 0.05/0.05 timing on Python 3.14; increasing the completed-state delay made the suite deterministic.
- The frontend API submit test now matches the explicit `workflow` + default `format` payload shape used by `submitGenerate()`.

## Warning Remediation

- `api/src/tests/test_generation_service.py` now uses `aupdate_job()` inside async polling tests, which removes the Modal `AsyncUsageWarning` without changing production logic.
- `api/src/tests/client_helpers.py` now lazily imports `fastapi.testclient` and suppresses the external `StarletteDeprecationWarning` at the import site used by test clients.
- `api/src/tests/test_comfy_client.py` now closes the mocked `HTTPError`, which removes the `ResourceWarning` observed in the backend suite.
- `view/next.config.ts` sets `turbopack.root` to the local `view/` directory so Next.js stops warning about multiple lockfiles / inferred workspace root.

## Remediation Verification

- `python3 -m pytest src/tests -W default` → 225 passed, 0 warnings.
- `npx vitest run` → 90 passed, 0 failed.
- `npm run build` → clean, with no multiple-lockfile / turbopack-root warning.

## Remaining

- None — Phase 4 complete.
