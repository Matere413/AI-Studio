# Tasks: Fix Orchestrator Selected Assets

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450-650 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 foundation → PR 2 backend validation → PR 3 frontend wiring/tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Add trusted selected-asset readiness and request DTO shape | PR 1 | Base backend readiness fields + shared contracts; include migration/backfill tests |
| 2 | Enforce deterministic planner/orchestrator selection rules | PR 2 | Base PR 1; selected metadata enrichment, ambiguity gates, atomic-flow allowlist |
| 3 | Fix frontend request mapping and regression coverage | PR 3 | Base PR 2 or tracker branch; dependency fix, DTO normalization, end-to-end request tests |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Add `upload_status` and `finalized_at` to `api/src/shared/models/persistence.py` and any required migration/backfill path for existing assets.
- [x] 1.2 Update `api/src/features/assets/service.py` to write trusted readiness only through upload/finalize paths, not client state.
- [x] 1.3 Extend `api/src/features/generation/models.py` with `SelectedAssetSummary` plus `selected_assets` while keeping `selected_asset_ids` canonical.

## Phase 2: Core Implementation

- [ ] 2.1 Enrich `api/src/features/generation/planner.py` with normalized selected-asset summaries and deterministic role rules for extraction/composition/identity.
- [ ] 2.2 Update `api/src/features/generation/orchestrator.py` to dedupe/normalize selections, validate trusted readiness, and block uploading/failed/unowned assets.
- [ ] 2.3 Add explicit ambiguity handling for multi-asset composition and identity/extraction collisions; return clarification instead of guessing.
- [ ] 2.4 Keep `flux2_editing` out of the allowlist and add a future-work marker in `openspec/development-plan.md`.

## Phase 3: Integration / Wiring

- [ ] 3.1 Update `view/src/features/chat/domain/dto.ts` and `view/src/features/chat/application/build-generate-request.ts` to emit deduped IDs plus filtered summaries.
- [ ] 3.2 Fix `view/src/app/page.tsx` request assembly so `selectedWorkflow` and `useTurbo` are included in callback dependencies.
- [ ] 3.3 Verify the frontend request maps only selected asset summaries and preserves legacy summary-poor requests.

## Phase 4: Testing / Verification

- [ ] 4.1 Add backend tests in `api/src/tests/test_orchestrator_agent.py` for readiness blocking, ambiguity questions, unselected-role rejection, and unsupported workflow rejection.
- [ ] 4.2 Add frontend tests in `view/src/features/chat/application/__tests__/build-generate-request.test.ts` for dedupe/filter behavior and stale dependency regression inputs.
- [ ] 4.3 Run the configured test suites for backend and frontend request-path coverage after the changes are wired together.

## Corrective Fixes (Fourth 4R Review Batch)

### Blocker 7 — Storage presign failure normalization
- [x] 7.1 `_resolve_async` in `app.py`: propagate storage/R2 infrastructure failures as infra errors, not user-correctable `ValueError`
- [x] 7.2 `dispatch_flow` in `service.py`: preserve `StorageError` as infrastructure failure while keeping `ValueError` for invalid assets
- [x] 7.3 Legacy `/generate` endpoint: catch resolver/download infrastructure exceptions as structured 5xx responses; preserve `ValueError` as 422
- [x] 7.4 RED → GREEN tests proving storage failures are observable as 5xx and terminal-state behavior is covered at service level

### Blocker 8 — Misleading service comments
- [x] 8.1 `request_upload_ticket` docstring: correct "pending" → "uploading"
- [x] 8.2 `finalize_asset` docstring: document fail-closed semantics
- [x] 8.3 `_allow_finalize_without_storage` comment: cross-ref to finalize_asset docstring

## Corrective Fixes (Final 4R — Batch 5)

### Blocker 9 — Bound `selected_assets` metadata before planner forwarding
- [x] 9.1 Add `max_length=36` to `SelectedAssetSummary.id`
- [x] 9.2 Add `max_length=255` to `SelectedAssetSummary.name`
- [x] 9.3 Add `max_length=50` to `SelectedAssetSummary.status`
- [x] 9.4 Add `max_length=2000` to `SelectedAssetSummary.description`
- [x] 9.5 Add `max_length=50` to `SelectedAssetSummary.tags` list; add per-tag 100-char limit via validator
- [x] 9.6 Add `max_length=50` to `OrchestrateRequest.selected_asset_ids`
- [x] 9.7 Add `max_length=20` to `OrchestrateRequest.selected_assets`
- [x] 9.8 8 new RED → GREEN tests proving each bound is enforced

### Blocker 10 — Legacy `/generate` R2 download failure → structured 5xx
- [x] 10.1 Wrap `urllib.request.urlopen(...).read()` in try/except → structured AppError 500 (`asset_download_failed`)
- [x] 10.2 2 RED → GREEN tests: network error + URL timeout → structured 500

### Blocker 11 — Typed endpoint spawn failure job orphaning
- [x] 11.1 Wrap `task_fn.spawn(...)` in try/except; mark job "error" on any exception
- [x] 11.2 2 new RED → GREEN tests: RuntimeError + ConnectionError from spawn → job terminal

## Corrective Fixes (Closure 4R — Batch 6)

### Closure Blocker 1 — `dispatch_flow` ModelNotCachedError orphan
- [x] C1.1 Broaden `except ValueError` → `except Exception` in `dispatch_flow` validation catch-block
- [x] C1.2 2 RED → GREEN tests: service + router level

### Closure Blocker 2 — `enqueue_modal_work` job orphaning
- [x] C2.1 Wrap entire `enqueue_modal_work` body in try/except Exception; marks job `"error"` with `error_code="modal_enqueue_failed"`
- [x] C2.2 Add catch-all `except Exception → HTTP 500` in `_handle_service_errors()`
- [x] C2.3 5 RED → GREEN tests: service (2) + router (3)

### Closure Blocker 3 — StorageError observability as infra error
- [x] C3.1 Remove `except StorageError → raise ValueError` conversion in `app.py:_resolve_async`
- [x] C3.2 Add `except StorageError: raise` in `dispatch_flow`'s resolver catch-all (before generic `except Exception`)
- [x] C3.3 Update existing tests: `test_composition_storage_presign_failure_returns_422` → `_500`; `test_dispatch_flow_marks_job_error_on_storage_presign_failure` → pytest.raises(StorageError)
- [x] C3.4 3 RED → GREEN tests: app.py StorageError propagation, composition StorageError → 500, ValueError still → 422

## Corrective Fixes (4R Rerun — Batch 7)

### Blocker 12 — Legacy `/generate` storage infrastructure misclassified as 422
- [x] 12.1 Change resolver `except Exception → HTTPException(422)` to structured AppError 500 for storage/infra failures (preserve `ValueError → 422` for user-correctable asset issues)
- [x] 12.2 Change download `except Exception → HTTPException(422)` to structured AppError 500 for `urlopen`/network/timeout/storage failures (infra errors, not user errors)
- [x] 12.3 Update `test_flux2_editing_with_storage_error_from_resolver_returns_422` → `_returns_500` with structured `asset_resolution_failed` assertion
- [x] 12.4 Update `test_flux2_editing_with_r2_download_failure_returns_422` → `_returns_500` with structured `asset_download_failed` assertion
- [x] 12.5 Update `test_flux2_editing_with_urlopen_timeout_returns_422` → `_returns_500` with structured `asset_download_failed` assertion
- [x] 12.6 All 422 user-correctable asset tests remain at 422 (backward compat verified)

## Corrective Fixes (Final 4R — Structured error contract)

### Blocker 13 — Legacy `/generate` storage/R2 5xx responses must be structured
- [x] 13.1 Replace legacy resolver/download `HTTPException(status_code=500, detail=...)` with `AppError` responses shaped as `{"error":{"code","detail"}}`
- [x] 13.2 Preserve 422 for user-correctable resolver `ValueError` / invalid asset cases
- [x] 13.3 Remove misleading router-level terminal-state comments/pass-only verification and assert structured dispatch 5xx where feasible
- [x] 13.4 Refresh review-facing OpenSpec docs with current behavior, current diff shortstat, and slice-scoped `size:exception`

## Corrective Fixes (4R Rerun — Doc Updates)

### Doc Blocker D1 — Record size:exception and rollback/fix-forward in review-facing docs
- [x] D1.1 Record `size:exception` approval for PR slice 1 in apply-progress and verify-report
- [x] D1.2 Add rollback/fix-forward notes for the oversized operational slice
- [x] D1.3 Record latest test count/status (726 passed, no regressions)
