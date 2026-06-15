## Exploration: Realistic Persona Workflow

### Current State

The ai-studio backend uses a **WorkflowEngine** that loads ComfyUI API-format JSON templates paired with YAML manifests. Each workflow lives in `api/src/workflows/{name}/` and contains `workflow.json` + `manifest.yaml`. The engine validates node references, applies runtime parameters, and enforces model whitelist + cache rules before spawning Modal GPU work.

Existing workflows:
- **txt2img** — SD1.5 base, 512×512, prompt + negative_prompt + checkpoint + seed + steps + width + height
- **img2img** — SD1.5 base, 512×512, adds `denoise` and `image_url`
- **controlnet** — SD1.5 base, 512×512, adds `control_image_url` and `control_strength`
- **product_premium** — SDXL (juggernautXL), 1024×1024 square / 720×1280 vertical, format-driven, checkpoint locked by manifest

The `WorkflowName` literal in `api/src/features/generation/models.py` gates allowed workflow aliases: `txt2img | img2img | controlnet | product_premium`. The generation service enforces manifest-declared parameters, whitelist validation, and pre-cached model resolution before any Modal spawn.

### Affected Areas

- `api/src/features/generation/models.py` — add `realistic_persona` to `WorkflowName` literal
- `api/src/workflows/realistic_persona/` — new directory with `workflow.json` and `manifest.yaml`
- `api/src/tests/test_workflow_templates.py` — add template + manifest validation tests
- `api/src/tests/test_workflow_engine.py` — add engine init + parameter tests
- `api/src/tests/test_generation_models.py` — add `GenerateRequest` validation for new workflow
- `api/src/tests/test_generation_router.py` — add router integration tests
- `api/src/tests/test_generation_service.py` — add service dispatch + whitelist tests
- `openspec/specs/workflow-engine/spec.md` — delta spec for new workflow
- Environment variable `ALLOWED_MODELS_JSON` — add `moodyRealMix_zitV7.safetensors` to checkpoints list

### Approaches

1. **New workflow `realistic_persona`** — Dedicated directory, JSON, and manifest with its own checkpoint default.
   - Pros: Clean semantic separation, matches existing `product_premium` pattern, easy to add FaceDetailer/IPAdapter nodes later, resolution and sampler tuned for the specific checkpoint
   - Cons: Requires updating `WorkflowName` literal, new tests, and whitelist
   - Effort: Medium

2. **Variant of `txt2img`** — Reuse txt2img workflow and pass `moodyRealMix` as a checkpoint override.
   - Pros: Minimal file changes, no new workflow directory
   - Cons: txt2img is SD1.5-oriented (512×512). The moodyRealMix checkpoint is 11.46 GB — likely SDXL/FLUX class, which expects 1024×1024. Resolution mismatch risks poor output or OOM. Also conflates generic txt2img with persona-specific semantics.
   - Effort: Low

3. **Extend `product_premium`** — Reuse product_premium structure but swap checkpoint and prompt style.
   - Pros: Already has SDXL dimensions and format support
   - Cons: `product_premium` explicitly ignores checkpoint overrides and is semantically locked to product photography. Mixing persona generation into it breaks the domain boundary and the format system (square/vertical) is not meaningful for persona portraits.
   - Effort: Low-Medium, but architecturally wrong

### Recommendation

**Approach 1 — create a dedicated `realistic_persona` workflow.** The codebase already uses dedicated workflows for distinct domains (`product_premium` for commercial products). A realistic persona workflow deserves its own semantic identity, checkpoint default, and room for future identity-preservation nodes (FaceDetailer, IPAdapter, InstantID). The 11.46 GB checkpoint strongly suggests SDXL/FLUX class, so the new workflow should default to 1024×1024 resolution and appropriate sampler settings (euler, 25–30 steps, CFG 4–7). This keeps the architecture clean and avoids polluting the generic txt2img pipeline.

### Risks

- **No ComfyUI inventory available**: The `comfyui-workflow-builder` skill references `state/inventory.json`, but this file does not exist in the skill directory or the project. This means we cannot pre-validate node `class_type` names or confirm model compatibility against the actual ComfyUI installation.
- **Unknown checkpoint behavior**: `moodyRealMix_zitV7.safetensors` is not a well-known public checkpoint. No community metadata is available for optimal CFG, sampler, steps, or VAE requirements. The workflow JSON will need empirical tuning.
- **VRAM pressure**: At 11.46 GB, the checkpoint alone consumes most of a T4’s 16 GB. Adding FaceDetailer (+2 GB) or IPAdapter (+2 GB) later may exceed T4 limits and require A100 scheduling or FP8 quantization.
- **Whitelist dependency**: The checkpoint must be added to `ALLOWED_MODELS_JSON` and physically pre-cached in the Modal Volume before the workflow can be used in production.

### Ready for Proposal

Yes. Proceed to `sdd-propose` for the `realistic-persona-workflow` change.

The orchestrator should tell the user: exploration is complete; the recommended path is a dedicated `realistic_persona` workflow. The user should be aware that the `comfyui-workflow-builder` skill cannot validate against a real inventory because `state/inventory.json` is missing, so node names and model compatibility will be validated by tests and manual review rather than automated inventory checks.
