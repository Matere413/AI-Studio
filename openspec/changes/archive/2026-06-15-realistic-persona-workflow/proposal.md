# Proposal: Realistic Persona Workflow

## Intent

Add a stable, UI/API-exposed workflow for realistic human persona generation across portraits, full-body, lifestyle, and editorial images. The workflow must support controllable demographics and styling while avoiding plastic, waxy, or overprocessed advertising-model output.

## Scope

### In Scope
- Add dedicated `realistic_persona` workflow contract with prompt plus persona controls: age, gender, ethnicity, wardrobe, expression, and background.
- Add ComfyUI template and manifest following the `product_premium` pattern, using `moodyRealMix_zitV7.safetensors` as the default checkpoint.
- Expose the workflow through existing generation API and frontend workflow selection.
- Validate manifest parameters, whitelist/cache behavior, and request routing with tests.

### Out of Scope
- FaceDetailer, IPAdapter, InstantID, or reference-image identity preservation in this slice.
- Runtime model downloads or automatic checkpoint metadata inference.
- Guaranteeing exact same-person identity across generations beyond seed/prompt consistency.

## Capabilities

### New Capabilities
- `realistic-persona-workflows`: Dedicated contract for realistic persona generation, supported controls, natural aesthetics, defaults, and identity-consistency boundaries.

### Modified Capabilities
- `image-generation`: Accept `workflow = "realistic_persona"` with declared persona controls.
- `workflow-engine`: Load and resolve the `realistic_persona` manifest/template without hardcoded node IDs.
- `model-weight-caching`: Whitelist and require pre-cached availability of `moodyRealMix_zitV7.safetensors`.
- `generative-ai-studio-frontend`: Expose the persona workflow and its stable controls in the UI.

## Approach

Create `api/src/workflows/realistic_persona/` with `workflow.json` and `manifest.yaml`, modeled after `product_premium` but semantically isolated. Default to T4-aware SDXL-like dimensions and conservative sampler settings, then route through the existing `WorkflowEngine`, `WorkflowName`, request validation, service dispatch, and UI workflow controls.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/workflows/realistic_persona/` | New | Template and manifest |
| `api/src/features/generation/` | Modified | Workflow enum, validation, dispatch |
| `view/` | Modified | Workflow option and persona controls |
| `api/src/tests/` | Modified | Template, engine, model, router, service tests |
| `openspec/specs/` | Modified/New | Capability deltas and new workflow spec |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missing ComfyUI inventory blocks automated node validation | High | Use existing template patterns and tests; manually verify in ComfyUI |
| Unknown checkpoint tuning due no metadata | Medium | Start conservative; tune sampler/CFG after empirical runs |
| T4 VRAM pressure from 11.46 GB checkpoint | Medium | Avoid extra identity/detailer nodes in V1 |

## Rollback Plan

Remove `realistic_persona` workflow files, enum/API/UI exposure, tests, and whitelist entry. Existing workflows remain unchanged because the new workflow is isolated by name and manifest.

## Dependencies

- `moodyRealMix_zitV7.safetensors` must be whitelisted and pre-cached in the Modal Volume.
- Manual ComfyUI validation is required until `state/inventory.json` exists.

## Success Criteria

- [ ] API accepts valid `realistic_persona` requests and rejects undeclared controls.
- [ ] Frontend exposes the workflow and persona controls without model selectors.
- [ ] Tests prove manifest loading, routing, whitelist/cache handling, and existing workflow preservation.
