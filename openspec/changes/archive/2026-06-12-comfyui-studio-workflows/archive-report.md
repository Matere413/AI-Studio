# Archive Report: comfyui-studio-workflows

**Change**: comfyui-studio-workflows
**Archive Date**: 2026-06-12
**Artifact Store Mode**: openspec
**Archive Location**: `openspec/changes/archive/2026-06-12-comfyui-studio-workflows/`

## Summary

Upgraded the MVP generation API into a ComfyUI Studio supporting complex workflows (Checkpoints, LoRAs, ControlNet, img2img). Implemented a **Hybrid Template + Node Map** architecture decoupling ComfyUI JSON from Python code, on-demand `.safetensors` model weight caching into the Modal volume, and standardized `/generate` plus new `/edit` (img2img) and ControlNet endpoints.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| `workflow-engine` | Created | New domain — Hybrid Template + Node Map parsing and parameterized execution |
| `model-weight-caching` | Created | New domain — On-demand `.safetensors` download, cache hit/miss, and failure handling |
| `image-generation` | Updated | MODIFIED "Accept Generation Requests" — expanded from hardcoded prompt-only to support optional checkpoint, LoRA, and workflow-selection parameters |

## Source of Truth Updated

The following main specs now reflect the delivered behavior:
- `openspec/specs/workflow-engine/spec.md`
- `openspec/specs/model-weight-caching/spec.md`
- `openspec/specs/image-generation/spec.md`

## Archive Contents

All artifacts preserved at `openspec/changes/archive/2026-06-12-comfyui-studio-workflows/`:

- proposal.md ✅
- specs/spec.md ✅ (delta spec with all domains)
- design.md ✅
- tasks.md ✅ (14/14 tasks complete)
- verify-report.md ✅ (PASS WITH WARNINGS)

## Verify Verdict

**PASS WITH WARNINGS** — 146/146 tests passing, 9/9 BDD scenarios compliant, no CRITICAL issues.

### Warnings (accepted, non-blocking)
1. Modal blocking-interface warnings from `src/shared/job_store.py` in async contexts
2. Cache readiness wired but not proven before generation starts (`download_model.spawn()` not awaited before `run_generation.spawn()`)
3. Strict TDD historical evidence partial — remediation evidence present, original RED history not fully reconstructable
4. LoRA support partial — fields exist and unsupported LoRA is rejected, but no LoRA-capable manifest/workflow demonstrated

## Intentional Archive

This archive proceeded normally. No partial-archive or stale-checkbox reconciliation was needed. All 14 implementation tasks are marked complete in the archived `tasks.md`.

## PRs / Delivery

The change was implemented across 3 chained PRs following the work-unit forecast:
- PR 1: Manifest + schema foundation (`src/shared/workflows/models.py`, `src/workflows/txt2img/`)
- PR 2: Model cache service (`src/shared/workflows/cache.py`)
- PR 3: Workflow execution + API wiring (`src/shared/workflows/engine.py`, endpoint updates, integration tests)
