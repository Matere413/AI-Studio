## Verification Report

**Change**: `fix-orchestrator-selected-assets`  
**Mode**: Strict TDD  
**Scope verified**: PR slice 1 / Unit 1 only — backend foundation plus corrective blockers 1–13 and doc blockers D1.1–D1.3.  
**Fresh verification date**: 2026-07-02  
**Latest revision**: Fresh-context final verification after final 4R pass — Risk PASS, Reliability PASS, Resilience PASS, Readability PASS with non-blocking findings only.  

### Completeness

| Dimension | Result | Details |
|---|---:|---|
| Full change tasks complete | Partial | Phase 1 tasks 1.1–1.3 and corrective blockers 1–13 plus D1.1–D1.3 are complete; Phase 2–4 planned work remains intentionally out of this slice. |
| Slice 1 tasks complete | ✅ | Phase 1 foundation and all corrective blocker checklist items are marked complete. |
| Prior 4R blockers | ✅ | Runtime evidence and source inspection confirm blockers 1–13 + doc blockers D1.1–D1.3 are resolved for this slice. |
| Review budget | ⚠️ | Current tracked diff is `3740 insertions + 146 deletions = 3886 changed lines` from `git diff --shortstat`; maintainer-approved `size:exception` recorded on 2026-07-01 for PR slice 1 only. Future slices MUST return to ≤400-line budget. |

### Build & Tests Execution

**Build**: ➖ Not run separately — this backend slice has no dedicated build command; runtime verification used pytest.

**Focused backend tests**: ✅ 269 passed (slice-1 focused model, asset service, persistence, generation service/router, and app tests)

```text
Command: python3 -m pytest src/tests/test_generation_models.py src/tests/test_assets_service_real.py src/tests/test_models.py src/tests/test_generation_service.py src/tests/test_generation_router.py src/tests/test_app.py --tb=short -q
Workdir: api
Result: 269 passed in 30.10s
```

**Full backend tests**: ✅ 726 passed

```text
Command: python3 -m pytest --tb=short -q
Workdir: api
Result: 726 passed in 49.18s
```

**Fresh full backend tests**: ✅ 726 passed

```text
Command: python3 -m pytest --tb=short -q
Workdir: api
Result: 726 passed in 53.62s
```

**Coverage**: ➖ Not available

```text
Command: python3 -m pytest src/tests/test_models.py src/tests/test_assets_service_real.py src/tests/test_generation_models.py --cov=src.shared.models.persistence --cov=src.features.assets.service --cov=src.features.generation.models --cov-report=term-missing
Result: pytest rejected --cov arguments; pytest-cov is not installed/enabled in this environment.

Fresh confirmation:
Command: python3 -m pytest src/tests/test_generation_models.py --cov=src.features.generation.models --cov-report=term-missing -q
Result: pytest rejected --cov arguments; pytest-cov is not installed/enabled in this environment.
```

### TDD Compliance

| Check | Result | Details |
|---|---:|---|
| Strict TDD mode used for verification | ✅ | Orchestrator stated Strict TDD is active; `openspec/config.yaml` also has `testing.strict_tdd: true`. |
| TDD evidence reported | ✅ | `apply-progress.md` includes a TDD Cycle Evidence table for corrective blockers 1–13. |
| RED confirmed | ✅ | Tests updated first to assert structured 5xx bodies before production code change. Initial run confirmed 4 failures: three legacy storage/R2 cases returned unstructured `{"detail": ...}` and one generic dispatch 500 lacked `error.code`. |
| GREEN confirmed | ✅ | Fresh execution: `269 passed` focused slice suite and `726 passed` full backend suite. |
| Triangulation adequate | ✅ | Final blockers cover 3 storage/infra failure paths (resolver StorageError, download network error, download timeout), generic dispatch 500 structure, and 2 preserved 422 user-error paths. |
| Safety net | ✅ | Full backend suite passed: 726/726 (same as baseline, no regressions). |

**TDD Compliance**: 6/6 checks passed.

---

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|---|---:|---:|---|
| Unit | Primary coverage for models/service/storage/persistence | 7 | pytest |
| Integration/API | FastAPI router and asset service DB tests | 3 | pytest + TestClient + async DB fixtures |
| E2E | 0 for this slice | 0 | Not required for backend Unit 1 |

---

### Changed File Coverage

Coverage analysis skipped — no coverage tool detected (`--cov` was not accepted by pytest).

---

### Assertion Quality

Reviewed the added/relevant tests for blockers 1–13. Assertions exercise production models, API endpoints, persistence helpers, storage wrappers, resolver behavior, structured error bodies, and service-level job terminal state. Misleading router-level pass-only terminal-state comments were removed or replaced with concrete structured response assertions.

**Assertion quality**: ✅ All reviewed assertions verify real behavior.

**Review artifact note**: OpenSpec change artifacts under `openspec/changes/` are currently local/ignored by Git unless explicitly force-added; PR reviewers should not assume this report or sibling change notes are included in the tracked PR diff by default.

---

### Quality Metrics

**Linter**: ➖ Not available

```text
Command: python3 -m ruff check src/shared/models/persistence.py src/features/assets/service.py src/features/generation/models.py src/features/generation/router.py src/features/generation/service.py src/tests/test_models.py src/tests/test_assets_service_real.py src/tests/test_generation_models.py src/tests/test_generation_router.py src/tests/test_generation_service.py
Result: /usr/local/bin/python3: No module named ruff

Fresh confirmation: same command, same result (`No module named ruff`).
```

**Type Checker**: ➖ Not run — no backend type-check command is configured for this slice.

### Spec Compliance Matrix

| Requirement | Scenario / Contract | Slice 1 Evidence | Result |
|---|---|---|---:|
| Structured Planning | Selected asset metadata exists for planner context | `SelectedAssetSummary` and `OrchestrateRequest.selected_assets` exist with bounded validation and passing tests. Planner forwarding/enrichment remains later-slice work. | ⚠️ PARTIAL |
| Structured Planning | Planner cannot use unselected assets | Out of scope for Unit 1 except canonical `selected_asset_ids` DTO foundation. | ➖ SKIPPED |
| Structured Planning | Malformed planner output rejected | Existing orchestrator behavior outside Unit 1; full suite passed. | ➖ SKIPPED |
| Clarification Before Execution | Ambiguous requests ask a question | Out of scope for Unit 1 / planned Unit 2. | ➖ SKIPPED |
| Missing Asset Guidance | Uploading/failed/missing/not-owned assets do not dispatch | Foundation readiness fields and resolver/dispatch failure handling are implemented and tested. Orchestrator UX guidance remains later-slice work. | ⚠️ PARTIAL |
| Typed Executor Boundary | Approved typed flows only; no raw graph/future flow execution | Existing typed dispatch boundary remains; direct typed endpoints now mark jobs terminal on validation/resolver/spawn failure. | ✅ |

**Compliance summary**: Slice 1 satisfies the backend foundation and corrective safety contracts, but it is not full-change verification. Planner/orchestrator/frontend behavior remains intentionally deferred.

### Prior 4R Blocker Verification

| Blocker | Result | Evidence |
|---|---:|---|
| 1. R2 redirect rejects unfinalized assets | ✅ | `AssetsService.get_asset_by_r2_key()` enforces `upload_status == finalized` and `finalized_at`; focused suite passed. |
| 2. Resolver normalizes missing/deleted/not-owned/not-ready failures and preserves storage infra failures | ✅ | `_wire_asset_resolver()` maps user-correctable asset service errors to `ValueError("invalid_artifact...")`; storage/R2 infrastructure failures remain distinguishable as infra errors. API/service tests cover safe 422 and structured 5xx outcomes. |
| 3. Legacy `/generate` handles not-ready/missing/storage/download failure `image_asset_id` gracefully | ✅ | `/generate` resolves before job creation; maps user-correctable `ValueError`/invalid_artifact to 422 and infrastructure failures (StorageError, download/network/timeout) to structured 500. Router tests pass. |
| 4. Typed generation endpoints do not orphan pending jobs on resolver/spawn failure | ✅ | `dispatch_flow()` marks jobs `error` on validation/resolver/spawn exceptions; service and router tests passed. |
| 5. Backfill has recovery/observability | ✅ | `backfill_asset_upload_status()` warns on affected rows; `recover_backfilled_assets()` verifies pending assets and logs verified/skipped outcomes; persistence tests passed. |
| 6. PostgreSQL `_column_exists` is schema-scoped | ✅ | PostgreSQL introspection query includes `AND table_schema = CURRENT_SCHEMA`; schema test passed. |
| 7. `selected_assets` metadata has bounded validation and planner forwarding is safe enough | ✅ | Field lengths/cardinality are bounded by Pydantic and tested; canonical IDs remain authoritative. |
| 8. OpenSpec docs truthful about tests, blockers, and size exception | ✅ | This verify report was refreshed with current Strict TDD evidence and exact current diff size; `size:exception` is explicitly required. |
| 12. Legacy `/generate` storage infra failures classified as 5xx, not 422 | ✅ | Resolver `StorageError` and download failures (`urlopen`/timeout) now return structured 500; ValueError/invalid_artifact still returns 422. 3 tests reclassified, 2 preserved. |
| 13. Legacy `/generate` storage/R2 5xx follows project error contract | ✅ | Resolver/download infrastructure failures assert `{"error":{"code":"asset_resolution_failed"|"asset_download_failed","detail":...}}`; generic dispatch 500 asserts `generation_dispatch_failed`. |

### Correctness / Design Coherence

| Design Decision | Followed? | Notes |
|---|---:|---|
| `selected_asset_ids` remains authoritative | ✅ | `selected_assets` is optional metadata only. |
| Client metadata is untrusted | ✅ | Readiness/authorization remain server-owned; metadata fields are bounded before planner use. |
| Trusted readiness through backend persistence | ✅ | `upload_status` and `finalized_at` exist; upload/finalize and resolver paths enforce readiness. |
| Storage proof before finalization | ✅ | `finalize_asset()` requires `R2Storage.object_exists()` unless explicitly in test/dev override mode. |
| Backfill/recovery is observable | ✅ | Warning/info logs and recovery helper are present. |
| Atomic flow scope maintained | ✅ | `openspec/development-plan.md` tracks Flux 2 editing selected-asset integration as future work. |

### Review-Size / PR Boundary

| Metric | Value |
|---|---:|
| Tracked files changed | 21 |
| Current tracked insertions | 3740 |
| Current tracked deletions | 146 |
| Current tracked changed lines | 3886 |
| Review budget | 400 |
| Budget result | ❌ Exceeds budget by ~9.7× |
| Required process state | `size:exception` approved for PR slice 1 only; future slices must not inherit it automatically |

### Issues Found

**CRITICAL**
- None.

**WARNING**
- `size:exception` has been explicitly approved for PR slice 1. The current tracked diff is 3886 changed lines against a 400-line review budget, so reviewers should treat this as an intentionally oversized exception, not the default for future slices.
- Full-change tasks 2.x–4.x are still incomplete. This is acceptable only because this verification is explicitly scoped to PR slice 1 / Unit 1.
- Blocker 12/13 (legacy storage 422→structured 5xx) was a gap from the previous closure batch C3, which addressed `app.py` and `dispatch_flow` paths but missed the inline error handling in the `/generate` endpoint. Reviewers should verify that no other error classification gaps exist before PR slice 1 closure.

**SUGGESTION**
- Add a direct unit test for `_wire_asset_resolver()` where `svc._storage.presigned_get()` raises `StorageError`; endpoint-level and service-level storage failure behavior is covered, but the exact app resolver conversion would benefit from a narrow regression test.

### Rollback / Fix-Forward

**Rollback plan**: Revert the `AppError` structured 5xx mappings in `router.py` for resolver/download/generic dispatch failures and restore prior test assertions if needed. No data migration, schema changes, or job state rollback required. Safe to roll back at any time.

**Fix-forward contract**: Any `except Exception` catch that handles storage, network, or timeout infrastructure failures MUST use structured 5xx responses. Catch-all `except Exception → 422` or `HTTPException(status_code=500, detail=...)` in HTTP handlers must be reviewed as a potential blocker. Future slices should never introduce 422-classified infrastructure errors or unstructured 5xx bodies.

### Verdict

**PASS WITH WARNINGS** — Slice 1 technical blockers are resolved and backend runtime evidence is clean (`726 passed`, unchanged from baseline). All storage/infrastructure errors in legacy `/generate` are now correctly classified as structured 5xx. Maintainer-approved `size:exception` is recorded for this oversized PR slice only; future slices must return to ≤400 changed lines.

Fresh-context final verification confirms no CRITICAL findings remain for PR slice 1 / Unit 1. Final 4R pass is reflected: Risk PASS, Reliability PASS, Resilience PASS, and Readability PASS with non-blocking warnings only.

### Recommended Next Action

Proceed to PR preparation for slice 1 using the recorded `size:exception`, then start Unit 2 (Phase 2 tasks) in a smaller stacked PR (≤400 changed lines).
