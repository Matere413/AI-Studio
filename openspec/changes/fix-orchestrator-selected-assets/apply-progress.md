# Apply Progress: fix-orchestrator-selected-assets — 4R Corrective Fixes (Sixth/4R Rerun Batch)

## PR Slice 1 / Unit 1: Foundation — 4R Corrective Fixes

### Slice Boundary
- Start: existing PR slice 1 work with Phase 1 tasks 1.1–1.3 implemented
- End: all 6 blockers from third 4R review + all 8 blockers from fourth/fifth 4R reviews + legacy storage 422→500 reclassification resolved
- Out of scope: frontend changes, flux2_editing, further `.atl` modifications, tasks 2.x–4.x

### Completed Tasks

#### Already Complete (Previous Batches)
- [x] 1.1 Asset readiness fields + migration/backfill (`persistence.py`)
- [x] 1.2 Trusted upload/finalize service paths (`service.py`)
- [x] 1.3 SelectedAssetSummary + selected_assets DTOs (`models.py`)

#### Blocker 1 — R2 redirect readiness enforcement
- [x] `get_asset_by_r2_key()` raises `AssetNotReadyError` for non-finalized assets
- [x] Existing test updated to finalize first; new `test_rejects_non_finalized_asset_by_r2_key` added

#### Blocker 2 — Asset resolver normalization
- [x] Added `AssetNotFoundError` and `ProjectOwnershipError` to `_resolve_async` except clause in `app.py`
- [x] All three service errors map uniformly to `ValueError("invalid_artifact: ...")`
- [x] Test covers 4 scenarios (3 error types + happy path)

#### Blocker 3 — Legacy `/generate` safe validation failure
- [x] Wrapped `_resolve_asset_url_cb` in try/except ValueError → HTTPException(422)
- [x] 2 tests: invalid artifact + generic ValueError

#### Blocker 4 — Direct typed endpoints job orphaning
- [x] Wrapped `dispatch_flow` validation section in try/except ValueError
- [x] Jobs marked as `"error"` with `error_code="dispatch_failed"` before re-raising
- [x] 2 tests: invalid artifact + unsupported workflow

#### Blocker 5 — Backfill recovery + observability
- [x] `backfill_asset_upload_status()` logs WARNING when rows affected
- [x] `recover_backfilled_assets()` helper: async `verify_exists` callback, upgrades verified pending to finalized, logs info/warning
- [x] 4 tests: logging on backfill, no log on zero backfill, recovery upgrades verified, recovery returns zeroes on empty

#### Blocker 6 — PostgreSQL `_column_exists` schema scope
- [x] Added `AND table_schema = CURRENT_SCHEMA` to `information_schema.columns` query
- [x] 1 test validates the schema filter is present in generated SQL

#### Blocker 7 — Storage presign failure normalization (Fourth 4R; later corrected)
- [x] Final behavior: user-correctable resolver `ValueError`/invalid asset cases return 422; storage/R2 infrastructure failures propagate as structured 5xx
- [x] `dispatch_flow` in `service.py`: preserves `StorageError` as infrastructure failure and keeps generic user-correctable resolver failures as `ValueError("invalid_artifact: ...")`
- [x] Legacy `/generate` endpoint in `router.py`: resolver/download infrastructure failures return structured `AppError` 500; resolver `ValueError` remains 422
- [x] Tests prove storage failures are observable as 5xx and terminal-state behavior is covered at service level

#### Blocker 8 — Misleading service comments (Fourth 4R)
- [x] `request_upload_ticket` docstring: corrected "pending" → "uploading" to match actual `ASSET_STATUS_UPLOADING` constant
- [x] `finalize_asset` docstring: documented fail-closed behavior — raises `StorageNotConfiguredError` when storage is not configured and `_allow_finalize_without_storage` is `False`
- [x] `_allow_finalize_without_storage` comment: cross-referenced to `finalize_asset` docstring for full semantics

#### Blocker 9 — Bound `selected_assets` metadata (Final 4R)
- [x] Added `max_length` constraints to all `SelectedAssetSummary` string fields (id=36, name=255, status=50, description=2000)
- [x] Added `max_length=50` to `tags` list + custom validator limiting each tag to 100 chars
- [x] Added `max_length=50` to `selected_asset_ids` and `max_length=20` to `selected_assets` on `OrchestrateRequest`
- [x] 8 new tests proving each bound is enforced (6 on `SelectedAssetSummary`, 2 on `OrchestrateRequest`)

#### Blocker 10 — Legacy `/generate` R2 download failure (Final 4R)
- [x] Wrapped `urllib.request.urlopen(...).read()` in try/except Exception → structured AppError 500 with `asset_download_failed`
- [x] 2 tests: `test_flux2_editing_with_r2_download_failure_returns_500` + `test_flux2_editing_with_urlopen_timeout_returns_500`, both asserting the structured error body

#### Blocker 11 — Typed endpoint spawn failure job orphaning (Final 4R)
- [x] Wrapped `task_fn.spawn(...)` in `dispatch_flow` in try/except Exception; marks job `"error"` with `error_code="dispatch_failed"` on any exception
- [x] 2 new tests: `test_dispatch_flow_marks_job_error_on_spawn_failure` + `test_dispatch_flow_marks_job_error_on_modal_infrastructure_failure`
- [x] Coverage includes both `RuntimeError` (generic) and `ConnectionError` (infrastructure) paths

#### Closure Blocker 1 (4R) — `dispatch_flow` ModelNotCachedError job orphaning
- [x] Broadened `except ValueError` → `except Exception` in `dispatch_flow`'s validation catch-block to catch `ModelNotCachedError` (which extends `Exception` directly, NOT `ValueError`)
- [x] Job now marked `"error"` with `error_code="dispatch_failed"` before re-raising on ModelNotCachedError
- [x] 1 new service-level test: `test_dispatch_flow_marks_job_error_on_model_not_cached`
- [x] 1 new router-level response-classification test: `test_composition_model_not_cached_returns_structured_500`; terminal-state verification remains covered at service level

#### Closure Blocker 2 (4R) — `enqueue_modal_work` job orphaning on any failure
- [x] Wrapped the entire `enqueue_modal_work` body in try/except Exception; marks job `"error"` with `error_code="modal_enqueue_failed"` before re-raising
- [x] Handles ModelNotCachedError, ValueError, RuntimeError (Modal spawn), and any other unexpected exception
- [x] 2 new service-level tests: model-not-cached + spawn failure
- [x] 2 new router-level tests: `/generate` model-not-cached + spawn failure (legacy endpoint job orphaning)
- [x] `_handle_service_errors()` in `router.py`: added catch-all `except Exception` → HTTP 500 to prevent unhandled exceptions from crashing the test harness

#### Closure Blocker 3 (4R) — StorageError observability as infrastructure error
- [x] Removed `except StorageError → raise ValueError` conversion in `app.py:_resolve_async` — StorageError now propagates as-is
- [x] Added `except StorageError: raise` in `dispatch_flow`'s inner resolver catch-all (BEFORE the generic `except Exception → raise ValueError`) so StorageError from the resolver is NOT masked as "invalid_artifact"
- [x] StorageError from resolver propagates through `dispatch_flow`'s outer `except Exception` (job marked `"error"`, error re-raised) → `_handle_service_errors()` → HTTP 500
- [x] Updated `test_composition_storage_presign_failure_returns_422` → renamed to `test_composition_storage_presign_failure_returns_500` and expects 500
- [x] Updated `test_dispatch_flow_marks_job_error_on_storage_presign_failure` → expects `pytest.raises(StorageError)` instead of `pytest.raises(ValueError)`
- [x] 2 new tests: `test_composition_storage_error_is_observable_as_500_not_missing_asset` + `test_storage_error_from_presigned_get_propagates_as_storage_error` (app.py)
- [x] 1 backward-compat test: `test_resolver_value_error_is_still_missing_asset`

#### Blocker 12 — Legacy `/generate` storage infrastructure misclassified as 422 (4R Rerun)
- [x] Resolver `except Exception → HTTPException(422)` changed to structured AppError 500 (`asset_resolution_failed`) for storage/infra failures from `_resolve_asset_url_cb`
- [x] Download `except Exception → HTTPException(422)` changed to structured AppError 500 (`asset_download_failed`) for `urlopen`/network/timeout/storage failures
- [x] `ValueError → HTTPException(422)` block preserved for user-correctable asset issues (`invalid_artifact`)
- [x] 3 tests updated: storage error, download failure, urlopen timeout all now assert status and structured body/code
- [x] Backward compat verified: existing 422 tests for ValueError/invalid_artifact still pass

#### Blocker 13 — Final 4R structured error contract + stale test/docs cleanup
- [x] Legacy `/generate` storage/R2 infrastructure failures now use the project error contract: `{"error": {"code": ..., "detail": ...}}`
- [x] `_handle_service_errors()` catch-all 500 now raises `AppError(code="generation_dispatch_failed")` instead of an unstructured `HTTPException`
- [x] Misleading router-level comments/pass-only terminal job verification were removed or replaced with real structured response assertions where feasible
- [x] OpenSpec docs refreshed to say asset/user problems → 422, storage/R2 infra failures → structured 5xx, and `size:exception` is slice-scoped

### TDD Cycle Evidence

| Blocker | Test | RED | GREEN | TRIANGULATE | REFACTOR |
|---------|------|-----|-------|-------------|----------|
| 1 (R2 redirect) | `test_rejects_non_finalized_asset_by_r2_key` | ✅ | ✅ | ✅ 1 case | N/A |
| 2 (Resolver errors) | `test_resolve_asset_url_maps_all_service_errors_to_value_error` | ✅ | ✅ | ✅ 4 cases | N/A |
| 3 (Legacy /generate) | `test_flux2_editing_with_invalid_image_asset_id_returns_422` + generic | ✅ | ✅ | ✅ 2 cases | N/A |
| 4 (Job orphaning) | `test_dispatch_flow_marks_job_error_on_validation_failure` + unsupported | ✅ | ✅ | ✅ 2 cases | N/A |
| 5 (Backfill) | `TestBackfillObservability` (2) + `TestRecoverBackfilledAssets` (2) | ✅ | ✅ | ✅ 4 cases | N/A |
| 6 (PG schema) | `test_pg_dialect_filters_by_table_schema` | ✅ | ✅ | ➖ Single | N/A |
| 7a (Storage presign) | `test_dispatch_flow_marks_job_error_on_storage_presign_failure` | ✅ | ✅ | ✅ 2 cases (storage + generic) | ✅ Clean |
| 7b (Legacy storage) | `test_flux2_editing_with_storage_error_from_resolver_returns_500` | ✅ | ✅ | ➖ Single case | ✅ Clean |
| 7c (Typed endpoint) | `test_composition_storage_presign_failure_returns_500` | ✅ | ✅ | ➖ Single case | ✅ Clean |
| 9a (ID length) | `test_rejects_id_exceeding_36_chars` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9b (Name length) | `test_rejects_name_exceeding_255_chars` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9c (Status length) | `test_rejects_status_exceeding_50_chars` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9d (Desc length) | `test_rejects_description_exceeding_2000_chars` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9e (Tags cardinality) | `test_rejects_too_many_tags` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9f (Tag length) | `test_rejects_tag_exceeding_100_chars` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9g (IDs cardinality) | `test_rejects_excessive_selected_asset_ids` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 9h (Assets cardinality) | `test_rejects_excessive_selected_assets` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 10a (R2 network) | `test_flux2_editing_with_r2_download_failure_returns_500` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 10b (R2 timeout) | `test_flux2_editing_with_urlopen_timeout_returns_500` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 11a (Spawn Runtime) | `test_dispatch_flow_marks_job_error_on_spawn_failure` | ✅ | ✅ | ➖ Single | ➖ None needed |
| 11b (Spawn infra) | `test_dispatch_flow_marks_job_error_on_modal_infrastructure_failure` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C1a (dispatch ModelNotCached) | `test_dispatch_flow_marks_job_error_on_model_not_cached` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C1b (comp model-not-cached) | `test_composition_model_not_cached_returns_structured_500` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C2a (enqueue ModelNotCached) | `test_enqueue_modal_work_marks_job_error_on_model_not_cached` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C2b (enqueue spawn) | `test_enqueue_modal_work_marks_job_error_on_spawn_failure` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C2c (legacy /generate not-cached) | `test_legacy_generate_model_not_cached_returns_structured_500` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C2d (legacy /generate spawn) | `test_legacy_generate_enqueue_spawn_failure_returns_structured_500` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C2e (legacy unsupported) | `test_legacy_generate_unsupported_workflow_returns_422` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C3a (app.py StorageError) | `test_storage_error_from_presigned_get_propagates_as_storage_error` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C3b (comp StorageError 500) | `test_composition_storage_error_is_observable_as_500_not_missing_asset` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C3c (ValueError still 422) | `test_resolver_value_error_is_still_missing_asset` | ✅ | ✅ | ➖ Single | ➖ None needed |
| C3d (existing: 422→500) | `test_composition_storage_presign_failure_returns_500` | ✅ | ✅ | ➖ Behavior change | ➖ Replaced |
| C3e (existing: ValueError→StorageError) | `test_dispatch_flow_marks_job_error_on_storage_presign_failure` | ✅ | ✅ | ➖ exception type | ➖ Updated |
| 12a (Resolver StorageError 422→500) | `test_flux2_editing_with_storage_error_from_resolver_returns_500` | ✅ | ✅ | ➖ Single (reclassify) | ➖ None needed |
| 12b (Download failure 422→500) | `test_flux2_editing_with_r2_download_failure_returns_500` | ✅ | ✅ | ➖ Single (reclassify) | ➖ None needed |
| 12c (URL timeout 422→500) | `test_flux2_editing_with_urlopen_timeout_returns_500` | ✅ | ✅ | ➖ Single (reclassify) | ➖ None needed |
| 12d (ValueError still 422) | `test_flux2_editing_with_invalid_image_asset_id_returns_422` | ✅ (existing) | ✅ (untouched) | ➖ Unchanged | ➖ Unchanged |
| 12e (Generic ValueError still 422) | `test_flux2_editing_with_generic_value_error_from_resolver_returns_422` | ✅ (existing) | ✅ (untouched) | ➖ Unchanged | ➖ Unchanged |
| 13a (Resolver structured 5xx) | `test_flux2_editing_with_storage_error_from_resolver_returns_500` | ✅ | ✅ | ➖ Body/code assertion | ➖ None needed |
| 13b (Download structured 5xx) | `test_flux2_editing_with_r2_download_failure_returns_500` + timeout | ✅ | ✅ | ✅ Network + timeout | ➖ None needed |
| 13c (Generic dispatch structured 5xx) | `test_legacy_generate_enqueue_spawn_failure_returns_structured_500` | ✅ | ✅ | ➖ Body/code assertion | ➖ None needed |

### Commands Run
- `python3 -m pytest src/tests/...::TestName --tb=short -q` (RED/GREEN cycle per test)
- `python3 -m pytest --tb=short -q` (full suite verification)

### Test Results (final)
- **726 passed** (maintained from closure baseline; 3 tests reclassified from 422→structured 500, no net change in test count)
- All existing tests pass — zero regressions
- Backward compat verified: `test_flux2_editing_with_invalid_image_asset_id_returns_422` still returns 422 for user-correctable invalid_asset
- Backward compat verified: `test_flux2_editing_with_generic_value_error_from_resolver_returns_422` still returns 422 for user-correctable ValueError

### Deviations from Design
**Minor deviation — defense-in-depth in `dispatch_flow`**: The implementation handles resolver exceptions defensively while preserving the final error-classification contract: `ValueError` remains user-correctable (422), `StorageError` remains infrastructure (structured 5xx), and unexpected non-storage resolver failures are converted to invalid-artifact validation errors in typed dispatch paths.

**Extension — spawn protection in `dispatch_flow`**: The existing try/except ValueError in `dispatch_flow` only covered validation. The `task_fn.spawn(...)` call was outside the protection boundary. This fix adds a separate try/except around `spawn` that catches any Exception and marks the job terminal. This is consistent with the pre-existing "job must not be orphaned" contract.

**Correction (Closure Blocker 3) — StorageError must NOT be masked as missing_asset**: The previous implementation (Blocker 7) intentionally converted `StorageError` → `ValueError` in `app.py:_resolve_async` so storage failures followed the same safe validation path as not-ready/missing/ownership failures. However, this masked infrastructure failures behind a user-facing "invalid artifact" error (422). The closure 4R review determined that storage infrastructure failures should produce 500 so operators can distinguish them from user-correctable asset issues. This change:
  - Restored StorageError propagation in `app.py:_resolve_async`
  - Added `except StorageError: raise` in `dispatch_flow`'s resolver catch-all (before the generic `except Exception → raise ValueError` catch-all)
- Updated `_handle_service_errors()` with catch-all `except Exception → structured AppError 500`
  - Existing test `test_composition_storage_presign_failure_returns_422` → 500 (renamed)

**Extension — `enqueue_modal_work` job orphaning (Closure Blocker 2)**: The previous implementation (Blocker 4) only protected `dispatch_flow` against job orphaning. The legacy `/generate` endpoint path via `enqueue_modal_work` had no protection. This fix wraps the entire `enqueue_modal_work` body in try/except Exception, marking the job terminal on any failure before re-raising.

**Extension — `_handle_service_errors()` catch-all (Closure Blocker 2)**: `_handle_service_errors()` previously only caught AppError, ModelNotAllowedError, ModelNotCachedError, and ValueError. Infra exceptions (StorageError, RuntimeError from Modal) were unhandled and would crash the test harness. Added catch-all `except Exception → structured AppError 500` as a safety net.

### Issues Found
**Blocker 12/13 (current batch)**: The legacy `/generate` endpoint's `except Exception` catch blocks for resolver failures and download failures were first reclassified from 422 to 500, then finalized under the project structured error contract.
- Resolver non-`ValueError` failures (StorageError, ConnectionError) now return structured 500 (`asset_resolution_failed`)
- Download/network failures (ConnectionError, URLError) now return structured 500 (`asset_download_failed`)
- `ValueError` from resolver still returns 422 — user-correctable asset issues preserved

**Previously recorded issues (carried forward)**:
- `ModelNotCachedError` extends `Exception` directly (not `ValueError`), so it was silently escaping the `except ValueError` catch in `dispatch_flow`.
- The extraction workflow manifest (`src/workflows/extraction/manifest.yaml`) has NO model inputs, so `resolve_cached_model` is never called in that path. The router test was rewritten to use `/generate/composition` response classification, while terminal-state assertions remain in service-level tests.
- The test `test_legacy_generate_enqueue_spawn_failure_returns_structured_500` was originally not possible because `RuntimeError` from Modal spawn was never caught by `_handle_service_errors()`. The catch-all `except Exception → HTTP 500` was needed for any test wanting a proper HTTP response from unhandled infra exceptions.

### Workload / PR Boundary
- Mode: chained PR slice (stacked-to-main) — `size:exception` approved for PR slice 1 only
- Current work unit: PR slice 1 / Unit 1 corrective fixes (final 4R — structured legacy storage 5xx)
- Boundary: starts from existing Phase 1 implementation, ends with legacy `/generate` storage/R2 infrastructure failures correctly classified as structured 5xx
- Cumulative review budget impact: `3740 insertions + 146 deletions = 3886 changed lines` across PR slice 1 at final verification (`git diff --shortstat`)
- Review-facing OpenSpec change artifacts under `openspec/changes/` are currently local/ignored by Git unless explicitly force-added; PR reviewers should not assume these notes are included in the tracked PR diff by default.
- **size:exception**: Maintainer-approved `size:exception` recorded on 2026-07-01 for PR slice 1 only; future stacked slices MUST return to smaller reviewable boundaries (≤400 changed lines)
- **Rollback**: Revert the `AppError` structured 5xx mappings in `router.py` and restore the previous test body assertions if needed. No data migration, no schema changes, no job orphaning risk from rollback.
- **Fix-forward**: Future slices should never introduce 422-classified infrastructure errors or unstructured 5xx API bodies. Any `except Exception` catch that handles storage/network/timeout failures MUST use a structured 5xx AppError. Reviewers should flag any catch-all `except Exception → 422` or `HTTPException(status_code=500, detail=...)` as a blocking concern.
