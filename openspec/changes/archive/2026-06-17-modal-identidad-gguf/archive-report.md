# Archive Report: modal-identidad-gguf

**Archived**: 2026-06-17
**Source**: `openspec/changes/modal-identidad-gguf/` → `openspec/changes/archive/2026-06-17-modal-identidad-gguf/`
**Mode**: OpenSpec
**Verdict**: intentional-with-warnings

## Intent

Enable the downloaded `identidad_gguf.json` ComfyUI workflow to run on the Modal backend, preserving identity with Flux GGUF + PuLID and improving faces with Impact Pack.

## Task Completion

| Metric | Value |
|--------|-------|
| Total tasks | 13 |
| Completed | 12 |
| Unchecked | 1 (4.2 — Manual Modal verification) |

**Task 4.2 Reconciliation**: Task 4.2 "Verify cached models exist in Modal Volume" remains unchecked. This is a manual deployment verification step requiring Modal GPU infrastructure — it cannot be executed in the local development environment. All 305 tests pass (18 identidad_gguf-specific), and the verify report verdict is PASS WITH WARNINGS. Archive proceeds with explicit orchestrator request and documentation that this is a deployment-level verification, not a code deficiency.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| `image-generation` | Updated | 1 requirement added (Accept Identity GGUF Workflow Requests) with 3 scenarios |
| `model-weight-caching` | Updated | 2 requirements added (Identity GGUF Checkpoint Whitelist Entry + GGUF Custom Node Installation) with 5 scenarios |
| `workflow-engine` | Updated | 2 requirements added (Load Identity GGUF Workflow Manifest + Resolve Identity GGUF Parameters) with 4 scenarios |

All three deltas contained only ADDED requirements — no MODIFIED, REMOVED, or RENAMED sections. Merge was clean append-only.

## Archive Contents

- `proposal.md` ✅ — Intent, scope, approach, risks, rollback
- `specs/` ✅ — 3 delta specs (image-generation, model-weight-caching, workflow-engine)
- `design.md` ✅ — Architecture decisions, data flow, file changes, contracts
- `tasks.md` ✅ — 12/13 tasks complete (1 manual Modal verification pending)
- `verify.md` ✅ — PASS WITH WARNINGS (305/305 tests, 18 identidad_gguf-specific)
- `archive-report.md` ✅ — This document

## Source of Truth Updated

- `openspec/specs/image-generation/spec.md`
- `openspec/specs/model-weight-caching/spec.md`
- `openspec/specs/workflow-engine/spec.md`

## Risks

- **Task 4.2 pending**: Manual verification of cached GGUF/PuLID/face_detector models on Modal Volume must be completed before first production deploy
- **Missing TDD Cycle Evidence**: The verify report flagged a missing `apply-progress` artifact (process concern, not code quality — all tests exist and pass)
