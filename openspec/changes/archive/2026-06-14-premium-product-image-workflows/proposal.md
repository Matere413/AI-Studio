# Proposal: Premium Product Image Workflows

## Intent

Enable high-quality image generation for commercial physical products while preserving a prompt-first experience. The first slice should improve premium studio and lifestyle/product-in-context outputs without exposing closed style menus or expanding infrastructure before T4/model limits are proven.

## Scope

### In Scope
- Define a premium physical-product workflow contract for free-form prompts, studio shots, and lifestyle/in-context imagery.
- Support square and vertical/social output formats with T4-safe defaults.
- Add a `product_premium` ComfyUI workflow using existing manifests and whitelisted pre-cached models.
- Prepare the contract for future reference-image-guided fidelity without requiring upload/storage work now.

### Out of Scope
- Public style preset menus, arbitrary model selection, or runtime model downloads.
- Custom upscalers/detailers, LoRA marketplace support, or A100-only workflows.
- Full reference-image ingestion/execution until storage and UX are designed.

## Capabilities

### New Capabilities
- `premium-product-image-workflows`: Prompt-first product imagery for physical goods, covering premium studio/lifestyle intent, output format choices, and staged fidelity expectations.

### Modified Capabilities
- `image-generation`: Accept product workflow intent and square/vertical format parameters while keeping existing clients compatible.
- `workflow-engine`: Support the new product workflow manifest and any declared product-specific parameters.
- `model-weight-caching`: Require any premium checkpoint to be whitelisted and pre-cached in the Modal Volume.
- `generative-ai-studio-frontend`: Keep prompt as the primary visible control; avoid closed style preset menus.

## Approach

Use the existing workflow engine. Specify a `product_premium` workflow with tuned sampler/CFG/resolution defaults, a whitelisted premium checkpoint, and two safe output formats. Treat studio vs lifestyle as prompt intent, not a visible preset. Reserve reference-image constraints for specs/design, then implement image-guided execution later.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/workflows/product_premium/` | New | Workflow JSON and manifest for product imagery. |
| `api/src/features/generation/` | Modified | Product workflow/format request fields and default resolution. |
| `api/src/shared/modal_config.py` | Modified | Premium checkpoint whitelist entry. |
| `view/src/` | Modified | Prompt-first controls; no style preset menu. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| T4 cannot handle target resolution | Med | Cap formats; profile before upscalers/A100. |
| Product fidelity is overpromised without references | High | State prompt-only limits; stage reference-image support explicitly. |
| Missing cached checkpoint blocks jobs | Med | Whitelist only pre-cached Volume assets; fail fast. |

## Rollback Plan

Remove the `product_premium` workflow/contract and whitelist entry; existing workflows remain unchanged.

## Dependencies

- ComfyUI Modal execution, workflow manifests, Modal Volume cache, approved premium checkpoint.

## Success Criteria

- [ ] Product requests use the new workflow without breaking existing clients.
- [ ] Square and vertical outputs are accepted.
- [ ] Specs/design clearly separate first-slice prompt quality from later reference-image fidelity.
