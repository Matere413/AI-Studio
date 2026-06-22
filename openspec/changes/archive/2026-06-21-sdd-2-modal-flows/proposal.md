# Proposal: SDD 2 Modal Flows

## Intent

Turn the backend Modal/ComfyUI pipeline into composable atomic flows for high-quality product image work. The current `GenerateRequest` and `GenerationService` centralize workflow-specific validation, routing, and image payload handling; SDD 2 introduces typed flow modules and disk/volume image artifacts so future orchestration can chain outputs without Base64 roundtrips.

## Scope

### In Scope
- Refactor API contracts around `BaseAtomicFlow` and per-flow Pydantic v2 request models.
- Add `ImageArtifact` for `volume_path | url | upload` image handoff, avoiding frontend Base64 as the primary path.
- Implement three backend flows: BRIA extraction to transparent PNG, FLUX + ControlNet Depth/Canny composition, and PuLID + FLUX identity.
- Upgrade Modal GPU profiles to L4/A100 where required and pin required ComfyUI node/model dependencies.
- Replace the legacy `identidad_gguf` identity flow with the new identity flow.

### Out of Scope
- Frontend UX for exposing these flows.
- Multi-step orchestrator/chaining UI.
- Upscaling, detailing, outpainting, and inpainting; defer to SDD 6.

## Capabilities

### New Capabilities
- `extraction-isolation-workflows`: BRIA-based subject/background extraction producing transparent PNG artifacts.
- `composition-workflows`: FLUX composition with ControlNet Depth/Canny using either prior extraction output or explicit upload.
- `identity-workflows`: PuLID + FLUX identity-preserving generation replacing legacy identity GGUF behavior.

### Modified Capabilities
- `workflow-engine`: add atomic-flow contract, manifest outputs, and artifact-aware image input mapping.
- `image-generation`: stop extending kitchen-sink `GenerateRequest`; route new flows through typed flow requests.
- `model-weight-caching`: whitelist and pre-cache BRIA, ControlNet, FLUX, PuLID, and required custom nodes.
- `identity-gguf-workflows`: deprecate/remove as the supported identity path.

## Approach

Use Option A from exploration: per-flow modules backed by shared `BaseAtomicFlow`. Keep `workflow.json` + `manifest.yaml`; extend manifests with outputs/artifacts. Store produced images in Modal volume and pass `ImageArtifact` references between flows. Keep legacy generation stable while introducing typed flow dispatch.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/shared/flows/` | New | BaseAtomicFlow, flow output contract |
| `api/src/shared/artifacts.py` | New | ImageArtifact model |
| `api/src/features/generation/*` | Modified | Remove if/else routing pressure |
| `api/src/workflows/` | New/Modified | Add three templates/manifests; replace identity |
| `api/src/shared/modal_config.py` | Modified | GPU profiles, pinned nodes/models |
| `openspec/specs/` | Modified | New flow specs + engine/model deltas |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Scope exceeds review budget | High | Split apply into seam, extraction, composition, identity PRs |
| Modal build/runtime instability | Med | Pin custom-node commits and validate cached models before spawn |
| VRAM pressure for FLUX + ControlNet/PuLID | High | Default heavy flows to L4/A100 profiles |
| Artifact path security bugs | Med | Validate artifact ownership, media type, and volume path boundaries |

## Rollback Plan

Keep existing `flux2_txt2img` and `flux2_editing` paths unchanged during rollout. If SDD 2 fails, disable new flow registrations and restore `identidad_gguf` until the new identity flow is stable.

## Dependencies

- BRIA extraction assets/nodes, FLUX + ControlNet Depth/Canny assets, PuLID + FLUX assets.
- Modal volume capacity and GPU availability for L4/A100.

## Success Criteria

- [ ] New flows validate through typed Pydantic v2 models, not `GenerateRequest` branching.
- [ ] Extraction output can feed composition via `ImageArtifact` without frontend Base64.
- [ ] Identity flow replaces `identidad_gguf` with equal or better quality.
- [ ] Upscaling/detailing/outpainting/inpainting remain explicitly deferred.
