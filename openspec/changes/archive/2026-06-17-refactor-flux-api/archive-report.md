# Archive Report: refactor-flux-api

**Archived**: 2026-06-17
**Mode**: OpenSpec (hybrid — filesystem + Engram)
**Source directory**: `openspec/changes/refactor-flux-api/` → `openspec/changes/archive/2026-06-17-refactor-flux-api/`
**Orchestrator**: User (explicit archive request)

---

## Intent

This archive finalizes the "Refactor Flux 2 Generation API" change. The change removed all legacy workflow support (Qwen, product_premium, realistic_persona, txt2img, controlnet, img2img), added Flux 2 text-to-image and editing workflows with the `use_turbo` toggle and `image_base64` input, and aligned the frontend to support only three workflows: `flux2_txt2img`, `flux2_editing`, and `identidad_gguf`.

## Intentional Partial Archive

The following artifacts were NOT present in the change directory at archive time:

- `proposal.md` — not persisted (change was implemented without a formal proposal artifact)
- `design.md` — not persisted (design coherence check was skipped in verify-report)
- `state.yaml` — not created for this change

These absences are recorded but do not block archive. The user explicitly requested archiving, and the verification report confirms all 35 implementation tasks were completed with full TDD compliance. No design document was needed for this mechanical refactor.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| flux2-workflows | **Created** | New main spec — 6 requirements, 14 scenarios (Flux 2 txt2img, editing, manifests, turbo toggle, base64 resolution) |
| image-generation | **Updated** | 1 MODIFIED requirement (Accept Generation Requests — narrowed to 3 supported workflows, added legacy workflow rejection scenario), 4 REMOVED requirements (Product, Realistic Persona, Optional Image Fallback, Qwen) |
| model-weight-caching | **Updated** | 1 ADDED requirement (Flux 2 Model Whitelist Entries — `flux2_dev_fp8mixed`, `mistral_3_small_flux2_bf16`, `full_encoder_small_decoder`, `Flux_2-Turbo-LoRA`), 5 REMOVED requirements (Premium Checkpoint, Realistic Persona, FaceID Adapter, IPAdapter Plus, Qwen) |
| workflow-engine | **Updated** | 1 MODIFIED requirement (Execute Parameterized Workflows — narrowed to 3 supported workflows), 2 ADDED requirements (Load Flux 2 txt2img manifest, Load Flux 2 editing manifest), 6 REMOVED requirements (Product Premium + Resolve, Realistic Persona + Resolve, Qwen + Resolve) |

### Removal Audit

All REMOVED requirements included `(Reason: ...)` and `(Migration: ...)` notes in the delta specs, satisfying the archive policy for destructive merges.

## Archive Contents

| Artifact | Status | Notes |
|----------|--------|-------|
| `apply-progress.md` | ✅ | 3 PR slices, TDD cycle evidence for all 7 phases |
| `specs/flux2-workflows/spec.md` | ✅ | Delta spec for new Flux 2 workflows domain |
| `specs/image-generation/spec.md` | ✅ | Delta spec for modified/removed requirements |
| `specs/model-weight-caching/spec.md` | ✅ | Delta spec for added/removed whitelist entries |
| `specs/workflow-engine/spec.md` | ✅ | Delta spec for added/modified/removed engine requirements |
| `tasks.md` | ✅ | 35/35 implementation tasks complete (0 unchecked) |
| `verify-report.md` | ✅ | PASS WITH WARNINGS — 205 backend / 161 frontend tests pass, 0 CRITICAL issues |

## Verification Gate

- **Task completion**: ✅ All 35 tasks marked `[x]` in tasks.md
- **Verify report issues**: ✅ PASS WITH WARNINGS — 0 CRITICAL, 3 WARNING (non-blocking)
- **Spec compliance**: 39/42 scenarios fully compliant, 3 PARTIAL (edge-case format validation)
- **TDD compliance**: 6/6 checks passed

## Source of Truth Updated

The following main specs now reflect the refactored behavior:

- `openspec/specs/flux2-workflows/spec.md` — **NEW** (Flux 2 workflow contracts)
- `openspec/specs/image-generation/spec.md` — **UPDATED** (3 supported workflows only)
- `openspec/specs/model-weight-caching/spec.md` — **UPDATED** (Flux 2 + identity whitelist only)
- `openspec/specs/workflow-engine/spec.md` — **UPDATED** (Flux 2 + identity engine contracts)

## SDD Cycle Complete

The change has been fully planned, implemented, verified, and archived. The system now serves only `flux2_txt2img`, `flux2_editing`, and `identidad_gguf` workflows through a simplified API surface.
