## Exploration: Identity Preservation for `realistic_persona` Workflow

### Current State

The `realistic_persona` workflow (shipped 2026-06-15) is a **prompt-only generation pipeline** with no identity preservation. It uses a simple SDXL txt2img graph:

```
CheckpointLoader (juggernautXL_ragnarok) → EmptyLatent → CLIP Encode → KSampler → VAE Decode → SaveImage
```

The manifest explicitly excludes `FaceDetailer`, `IPAdapter`, `InstantID`, and `reference-image identity preservation` as V1 out-of-scope items. Identity consistency is achieved only via seed + prompt repetition, which is fragile and does not produce the same person across different prompts or poses.

The API already supports `image_url` parameter (used by `img2img` and `controlnet` workflows), but the `realistic_persona` workflow template does not consume it. The Modal generation function is hardcoded to `gpu="T4"` (16 GB VRAM).

### Affected Areas

- `api/src/workflows/realistic_persona/workflow.json` — must add identity-preservation nodes (Load Image → IP-Adapter/InstantID → KSampler)
- `api/src/workflows/realistic_persona/manifest.yaml` — must declare `image_url` input and remove `v1_excluded_nodes` block
- `api/src/shared/workflows/engine.py` — no changes needed; engine handles arbitrary node injection via manifest
- `api/src/features/generation/service.py` — `enqueue_modal_work` already accepts `image_url`; must validate it for `realistic_persona` and pass it to params
- `api/src/features/generation/models.py` — `GenerateRequest` may need `image_url` field made available for persona workflow (currently accepted but not validated for persona scope)
- `api/src/features/generation/modal_tasks.py` — `run_generation` uses `gpu="T4"`; identity workflows may require A100 routing
- `api/src/shared/modal_config.py` — `comfy_image` needs `ComfyUI_IPAdapter_plus` and `ComfyUI_InstantID` custom nodes installed
- `view/src/features/generation/api/types.ts` — may need `image_url` in `GenerationParameters` for persona workflow
- `view/src/features/generation/components/PromptPanel.tsx` — UI needs reference image upload for persona workflow
- `view/src/features/generation/stores/generationStore.ts` — must not strip `image_url` for persona workflow
- Modal Volume whitelist — must add IP-Adapter / InstantID / CLIP Vision / InsightFace model filenames

### Approaches

#### 1. IP-Adapter FaceID Plus V2 (SDXL)

**Description**: Add `ComfyUI_IPAdapter_plus` custom nodes. Load a reference face image, apply IP-Adapter FaceID Plus V2 with paired LoRA, and inject identity into the SDXL pipeline. Uses existing `juggernautXL_ragnarok.safetensors` checkpoint.

**VRAM estimate (T4)**:
- Base model (juggernautXL): ~6.5 GB
- IP-Adapter FaceID Plus V2: ~1.2 GB
- CLIP Vision ViT-H-14: ~3.4 GB
- Paired LoRA: ~200 MB
- **Total: ~11.3 GB** → fits comfortably on T4

**Pros**:
- Fits comfortably within T4 16 GB VRAM
- Fastest inference of the three options
- Minimal custom node surface (one node pack)
- No checkpoint migration needed; stays on SDXL
- Good baseline identity preservation per skill
- Auto-loads paired LoRA for better face consistency

**Cons**:
- Lower identity fidelity than InstantID or PuLID
- Single-face reference only (no multi-face)
- No style/pose control built-in (would need additional ControlNet)
- CLIP Vision model is large (~3.4 GB) for the gain it provides

**Effort**: Low

---

#### 2. InstantID + IP-Adapter FaceID (SDXL)

**Description**: Install `ComfyUI_InstantID` and `ComfyUI_IPAdapter_plus`. Extract identity keypoints with InstantID, blend with IP-Adapter FaceID for consistency, then generate. This is the skill's recommended "Zero-Shot Character Generation" pattern.

**VRAM estimate (T4)**:
- Base model (juggernautXL): ~6.5 GB
- InstantID ip-adapter.bin: ~4 GB
- InstantID ControlNet: ~4 GB
- InsightFace (antelopev2): ~200 MB
- IP-Adapter (if stacked): ~1.2 GB
- **Total: ~15.9 GB** → extremely tight on T4; high OOM risk

**Pros**:
- Highest identity fidelity among SDXL-based methods
- Proven in production for 3D→realistic conversion
- Supports pose control via bundled ControlNet
- Skill calls it "still excellent" despite maintenance mode
- Best for reference-image-driven generation

**Cons**:
- **OOM risk on T4** (~15.9 GB vs 16 GB limit)
- Requires two custom node packs + InsightFace models
- Slower than IP-Adapter alone
- Maintenance mode (no active development)
- Would likely require A100 for reliable operation

**Effort**: Medium

---

#### 3. PuLID Flux II (FLUX)

**Description**: Migrate the workflow from SDXL to FLUX.1-dev, install PuLID custom nodes, and use contrastive alignment for identity preservation with no model pollution.

**VRAM estimate (T4)**:
- FLUX.1-dev FP16: ~23.8 GB
- PuLID model: ~2 GB
- EVA-CLIP: ~3 GB
- **Total: ~28.8 GB** → impossible on T4
- FP8 quantized FLUX: ~10 GB + 2 GB + 3 GB = ~15 GB → tight, risky, requires FP8 support

**Pros**:
- Highest fidelity identity preservation available
- No model pollution (contrastive alignment)
- Supports dual characters
- State-of-the-art 2026 method

**Cons**:
- **Impossible on T4** (requires A100 exclusively)
- Requires full checkpoint migration from SDXL to FLUX (23.8 GB download)
- Slower generation than SDXL
- Requires FP8 quantization or A100 for any chance on mid-range GPUs
- Would need to replace `juggernautXL_ragnarok` with `flux1-dev.safetensors` and add T5/CLIP-L/VAE
- Completely breaks existing prompt aesthetics tuned for SDXL

**Effort**: High

---

### Recommendation

**Use IP-Adapter FaceID Plus V2 (SDXL) as the default identity preservation method.**

**Rationale**:
1. **T4 compatibility**: At ~11.3 GB total, it fits comfortably on our default T4 infrastructure without OOM risk. This is the only approach that works reliably on our current hardware.
2. **Checkpoint continuity**: We keep `juggernautXL_ragnarok.safetensors` — no migration, no re-tuning prompts, no 23 GB download.
3. **Speed**: Lowest latency of the three options, which matters for user experience in a studio UI.
4. **Quality is sufficient**: For realistic persona generation (not celebrity impersonation or forensic identity), IP-Adapter FaceID provides good enough consistency.
5. **Custom node surface**: Only one node pack (`ComfyUI_IPAdapter_plus`) vs two or more for InstantID.

**Future path**: Add an `identity_fidelity` parameter (or `gpu_tier` selector) that routes to A100 + InstantID when users need higher fidelity. Do NOT attempt PuLID/FLUX until the infrastructure is prepared for A100-only workflows.

### Risks

- **T4 OOM if InstantID is added later without A100 routing**: The workflow must be gated to IP-Adapter-only on T4.
- **CLIP Vision model missing from Modal Volume**: `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` (~3.4 GB) and `ip-adapter-plus-face_sdxl_vit-h.safetensors` (~1.2 GB) must be pre-cached. If missing, `model_not_cached` error will fire.
- **Custom node installation failure**: `ComfyUI_IPAdapter_plus` must be installed in the Modal image build. If the node is incompatible with the ComfyUI version, the workflow will fail at execution time.
- **Image URL handling**: The current API accepts `image_url` but the workflow template does not consume it. We must add a `LoadImage` node that can fetch from URL or the Modal Volume.
- **Identity preservation is not guaranteed**: IP-Adapter provides *likeness* consistency, not pixel-perfect identity. Users may expect exact face matching.
- **Front-end reference image upload**: The UI currently has no image upload for the persona workflow. Adding a file picker changes the component surface.
- **Prompt pollution**: If the reference image prompt is not properly weighted, the generated image may overfit to the reference background/clothing instead of the prompt.

### Ready for Proposal

**Yes.** The exploration is complete and the path is clear. The orchestrator should tell the user:

> We explored three identity preservation methods for `realistic_persona`. The winner is **IP-Adapter FaceID Plus V2 on SDXL** because it is the only method that fits reliably on our default T4 GPUs (~11.3 GB total) while providing good identity consistency. InstantID is higher fidelity but OOMs on T4. PuLID/FLUX requires A100 exclusively. We recommend adding a reference-image upload to the UI, installing `ComfyUI_IPAdapter_plus` in the Modal image, and caching the IP-Adapter + CLIP Vision models in the Modal Volume.

The next step is **sdd-propose** to formalize the scope, or **sdd-spec** if the scope is already clear.
