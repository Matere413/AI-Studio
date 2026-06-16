# Proposal: Qwen Text-to-Image Pipeline

## Intent

Add a Qwen Image text-to-image workflow for clients that need higher-fidelity prompt generation than the existing generic `txt2img`, while preserving the current async Job ID + webhook lifecycle. The API must let clients choose output dimensions and speed/quality tradeoff per request instead of forcing fixed template values.

## Scope

### In Scope
- Add `qwen_txt2img` as a selectable generation workflow.
- Expose dynamic `width` and `height` request parameters; do not hardcode resolution.
- Expose a quality mode flag: fast Lightning mode (4 steps) or high quality mode (50 steps).
- Keep execution asynchronous via existing job spawning, state tracking, and webhook callback pattern.
- Add Qwen FP8 UNET, Qwen CLIP, VAE, and Lightning LoRA model validation/caching requirements.

### Out of Scope
- Blocking/synchronous inference responses.
- Runtime model downloads in V1.
- Installing custom ComfyUI switch/primitive nodes from the source workflow.
- Frontend UI changes beyond API contract support.

## Capabilities

### New Capabilities
- `qwen-text-to-image-workflows`: Qwen-specific text-to-image workflow contract, dynamic dimensions, and quality-mode behavior.

### Modified Capabilities
- `image-generation`: accept `qwen_txt2img` requests with `width`, `height`, and quality mode while returning `202` + `job_id`.
- `workflow-engine`: resolve Qwen workflow parameters through manifest-backed node mappings.
- `model-weight-caching`: whitelist and require pre-cached Qwen model files and Lightning LoRA.

## Approach

Use the exploration’s simplified-template approach: convert the provided flat Qwen graph into the existing wrapped ComfyUI API template format, remove custom switch nodes, and map `prompt`, `negative_prompt`, `width`, `height`, and quality mode through the workflow manifest/service layer. Quality mode selects sampler defaults and whether the Lightning LoRA path is used, without bypassing the hexagonal workflow engine.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/workflows/qwen_txt2img/` | New | Qwen template and manifest |
| `api/src/features/generation/models.py` | Modified | Request contract/workflow enum |
| `api/src/features/generation/service.py` | Modified | Quality-mode parameter resolution |
| `api/src/shared/workflows/` | Modified | Manifest validation for Qwen mappings if needed |
| Modal model volume/config | Modified | Qwen model whitelist/cache prerequisites |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missing Qwen weights | Med | Validate whitelist and cache before spawning |
| High-quality mode exceeds timeout/GPU budget | Med | Keep async execution; verify timeout/GPU sizing |
| Invalid dimensions cause ComfyUI failure | Med | Validate ranges/multiples before execution |

## Rollback Plan

Remove `qwen_txt2img` from the allowed workflow list and deployment config, leaving existing workflows unchanged. Delete the workflow directory and Qwen whitelist entries if unused.

## Dependencies

- Qwen FP8 UNET, Qwen CLIP, Qwen VAE, and Lightning LoRA pre-cached in Modal Volume.
- Existing async Job ID + webhook infrastructure.

## Success Criteria

- [ ] `qwen_txt2img` requests return `202 Accepted` with `job_id` and never block on inference.
- [ ] Clients can set `width`, `height`, and fast/high-quality mode per request.
- [ ] Missing or non-whitelisted Qwen models fail before GPU execution.
