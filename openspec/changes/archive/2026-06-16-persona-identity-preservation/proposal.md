# Proposal: Persona Identity Preservation

## Intent

Upgrade `realistic_persona` with optional reference-face identity preservation so users can reuse the same person across prompts, poses, and persona variations on Modal T4 GPUs, while prompt-only generation continues unchanged when no face image is uploaded.

## Scope

### In Scope
- Switch `realistic_persona` default base model to `RealVisXL_V4.0`.
- Add SDXL IP-Adapter FaceID Plus V2 identity conditioning from an optional reference face image.
- Add frontend reference-face upload with session-state reuse across generations.
- Use prompt-only fallback when no reference face image is uploaded, generating a normal image from the text prompt and controls exactly as today.
- Keep existing persona controls enabled as testing overrides.

### Out of Scope
- InstantID, PuLID, FLUX, A100 routing, multi-face identity, or video identity.
- AI orchestrator inference of persona controls.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `realistic-persona-workflows`: Extend V1 prompt-only behavior with optional RealVisXL + FaceID conditioning and prompt-only fallback.
- `model-weight-caching`: Add RealVisXL_V4.0 and FaceID Plus V2 SDXL assets to Modal Volume/whitelist rules.
- `generative-ai-studio-frontend`: Add optional upload and session reuse while preserving controls.
- `image-generation`: Accept optional `image_url` for `workflow = "realistic_persona"`; fall back to prompt-only generation when absent.

## Approach

Use `ComfyUI_IPAdapter_plus` on Modal T4. Update the persona graph to load `RealVisXL_V4.0`, apply FaceID Plus V2 SDXL conditioning only when a face image is provided, and otherwise use the prompt-only fallback with the existing text prompt and controls. Store uploaded references in frontend session state and send the URL with persona requests when available.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/workflows/realistic_persona/` | Modified | Graph, manifest inputs, default checkpoint. |
| `api/src/features/generation/` | Modified | Accept/forward optional persona `image_url`; preserve prompt-only fallback when absent. |
| `api/src/shared/modal_config.py` | Modified | Install nodes; whitelist/cache weights. |
| `view/src/features/generation/` | Modified | Optional upload UI, session state, payload typing. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missing Modal Volume weights | Med | Pre-cache RealVisXL and FaceID assets; fail fast with existing cache errors. |
| T4 VRAM pressure | Med | Keep method to IP-Adapter-only SDXL; avoid InstantID/FLUX. |
| Exact clone expectations | Med | Position as likeness preservation, not forensic identity. |

## Rollback Plan

Revert the persona graph/manifest to `juggernautXL_ragnarok` prompt-only generation, hide upload UI, and remove new whitelist entries after active jobs drain.

## Dependencies

- `RealVisXL_V4.0`, `ComfyUI_IPAdapter_plus`, and FaceID Plus V2 SDXL assets cached/available on Modal.

## Success Criteria

- [ ] `realistic_persona` generation succeeds without a reference face image via prompt-only fallback.
- [ ] Uploaded face image persists for the session and is reused without re-uploading.
- [ ] Persona requests use RealVisXL_V4.0 + IP-Adapter FaceID Plus V2 on T4.
- [ ] Existing persona controls remain visible, enabled, and submitted as overrides.
