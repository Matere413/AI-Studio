# Exploration: Premium Product Image Workflows

## Current State

The generation pipeline is real and functional after `comfyui-real-integration`. It executes ComfyUI on Modal T4 GPUs with a 300-second timeout.

- **Workflow storage**: Static ComfyUI API-format JSON templates live under `api/src/workflows/{name}/workflow.json`, paired with a YAML manifest (`manifest.yaml`) that maps semantic inputs to node IDs and fields.
- **Current workflows**: `txt2img`, `img2img`, `controlnet`. All are basic pipelines using `CheckpointLoaderSimple`, `KSampler` (euler, 20 steps, cfg 8), `EmptyLatentImage` (512x512), `CLIPTextEncode`, `VAEDecode`, and `SaveImage`.
- **Model whitelist**: Enforced via `ALLOWED_MODELS_JSON` env var (default in `modal_config.py`). Default checkpoints: `epicrealism_naturalSinRC1VAE.safetensors`, `v1-5-pruned-emaonly-fp16.safetensors`. No LoRAs whitelisted.
- **Model cache**: `resolve_cached_model` checks the Modal Volume at `/root/ComfyUI/models/{type}/`. V1 boundary: no runtime downloads. Cache miss raises `model_not_cached`.
- **Job state model**: `modal.Dict` store with statuses `pending → booting_server → downloading_weights → generating → progress → completed/error`. `JobEvent` schema validates these strictly.
- **API contract**: `POST /generate` accepts `prompt`, optional `checkpoint_url`, `lora_url`, and `workflow_name` (default `txt2img`). `WS /ws/generate/{job_id}` streams granular lifecycle events.

## Affected Areas

- `api/src/workflows/txt2img/workflow.json` — baseline for comparison; current output is 512x512 with basic sampling.
- `api/src/workflows/product_premium/` — **new workflow directory** needed for high-quality physical product generation.
- `api/src/shared/workflows/models.py` — `WorkflowRequest` may need new semantic fields (e.g., `sampler`, `cfg`, `upscale_factor`) if the manifest declares them.
- `api/src/features/generation/models.py` — `GenerateRequest` may need to accept new workflow parameters or a `preset` field.
- `api/src/shared/modal_config.py` — whitelist JSON must be updated to include premium product checkpoints (e.g., SDXL realistic or product-specific models). GPU type might need review for higher resolution.
- `api/src/shared/workflows/cache.py` — no logic change, but pre-cached volume must contain the new model files before deployment.
- `api/src/features/generation/service.py` — `enqueue_modal_work` validates parameters against the manifest. New workflows must be validated here.
- `api/src/features/generation/modal_tasks.py` — `run_generation` runs on `gpu="T4"`. Higher resolution workflows may exceed T4 VRAM or the 300s timeout.

## Approaches

### 1. Enhanced Workflow JSON (Same Engine, Better Defaults)
**Description**: Create a new `product_premium` workflow directory with an improved ComfyUI JSON graph: higher default resolution (1024x1024), better sampler (e.g., `dpmpp_2m` or `euler_ancestral`), optimized CFG (7–8), and a better default checkpoint. Expose new parameters via the manifest so the API can override them.

- **Pros**:
  - Reuses the existing `WorkflowEngine` and `ManifestSchema` with zero engine changes.
  - Minimal code change — mostly new JSON/YAML artifacts.
  - Easy to A/B test against the current `txt2img` workflow.
- **Cons**:
  - Limited by the existing node set. No upscaling or detail enhancement unless custom nodes are added.
  - Does not improve model quality if the checkpoint itself is not product-optimized.
  - T4 GPU may struggle with 1024x1024 if the checkpoint is large (SDXL).
- **Effort**: Low

### 2. Add Upscaler + Detailer Nodes to Workflow
**Description**: Extend the premium workflow with ComfyUI upscaler nodes (e.g., `LatentUpscale` or `ImageUpscaleWithModel`) and a detailer/refiner pass. This produces higher-resolution marketing-ready images.

- **Pros**:
  - Significant quality improvement for physical products (sharpness, detail).
  - Keeps everything in a single workflow execution.
- **Cons**:
  - Requires installing custom nodes or upscaler models into the Modal image/Volumes.
  - **VRAM risk**: Upsampling + base diffusion on a T4 can exceed 16 GB.
  - **Timeout risk**: Two-stage generation (base + upscale) may exceed the 300s pipeline timeout.
  - Increases workflow complexity and manifest size.
- **Effort**: Medium

### 3. Upgrade GPU + Model Tier (T4 → A100, SD1.5 → SDXL)
**Description**: Switch the Modal GPU to A100 (40 GB) and add an SDXL or product-specific realistic checkpoint to the whitelist. Update the workflow to target SDXL resolution (1024x1024 natively). Keep the graph simple but leverage the stronger model.

- **Pros**:
  - Best raw image quality from the model itself.
  - A100 handles high resolution and larger checkpoints easily.
  - No workflow complexity increase.
- **Cons**:
  - **Cost increase**: A100 is significantly more expensive per inference.
  - **Volume size**: SDXL checkpoints are ~7 GB; adding multiple variants increases Modal Volume size and cold-start cache validation time.
  - **Infrastructure change**: Switching GPU type affects the entire Modal function, not just one workflow.
  - May need to keep T4 for basic workflows and use A100 only for premium, requiring two Modal functions.
- **Effort**: Medium

### 4. Preset-Based API (Parameter Bundles)
**Description**: Instead of exposing every sampler/CFG node to the client, add a `preset` field to `GenerateRequest` (e.g., `preset: "product_premium"`). The service maps the preset to a workflow + default parameters. The client only sends `prompt` and `preset`.

- **Pros**:
  - Simpler API for marketing users.
  - Encapsulates quality tuning internally (sampler, steps, cfg, negative prompt).
  - Easy to extend with new presets later.
- **Cons**:
  - Requires changes to `GenerateRequest`, `GenerationService`, and possibly the job store to track the preset.
  - Presets are hardcoded in Python unless a dynamic registry is built.
- **Effort**: Low

## Recommendation

**Approach 1 (Enhanced Workflow) + Approach 4 (Preset API) as the first slice.**

- Add a `product_premium` workflow with 1024x1024 default, `euler_ancestral` or `dpmpp_2m`, CFG 7, and a product-optimized checkpoint (e.g., a realistic SDXL or SD1.5 fine-tune). Keep it within the existing node set to avoid custom node installation.
- Add a `preset` field to `GenerateRequest` so the client can simply call `{"prompt": "...", "preset": "product_premium"}`. The service resolves the preset to the `product_premium` workflow with its defaults.
- Update the whitelist in `modal_config.py` to include the new checkpoint.
- **Defer upscaling (Approach 2)** to a later slice after we verify T4 VRAM and timeout at 1024x1024.
- **Defer GPU upgrade (Approach 3)** until cost/benefit is proven with real usage metrics.

## Risks

- **GPU Memory / T4 Limit**: 1024x1024 with SDXL on T4 is near the 16 GB limit. If the checkpoint is large and we increase batch size or resolution, OOM is likely. Mitigation: test with SD1.5 product fine-tune first, or upgrade to A100.
- **Model Cache Size / Volume Growth**: Each new checkpoint adds ~4–7 GB to the Modal Volume. The `download_model` helper is not used in V1, so models must be pre-cached manually. Risk of forgetting to cache the model before deploy.
- **Workflow Asset Complexity**: Adding custom nodes (e.g., for upscaling or detailers) requires modifying `modal_config.py` `comfy_image` to `git clone` or `pip install` them. This increases image build time and risk of node incompatibilities.
- **300-Second Timeout**: If the premium workflow uses more steps or larger resolution, inference time increases. The 300s hard timeout includes ComfyUI boot. Mitigation: profile inference time first; increase timeout if needed.
- **Review Budget (400 lines)**: Adding a new workflow, preset logic, tests, and whitelist updates can easily exceed 400 lines. Mitigation: deliver the first slice as a single focused PR (workflow + preset + tests), keep changes minimal.
- **Backward Compatibility**: Existing `txt2img` / `img2img` / `controlnet` clients must continue working unchanged. The `preset` field should be optional and default to current behavior.

## Ready for Proposal

**Yes.** The exploration confirms the codebase is well-structured for this refinement. The `WorkflowEngine` and manifest system make adding a new workflow a low-risk, additive change. The main architectural decisions needed are:
1. Which exact checkpoint to whitelist for physical products.
2. Whether the T4 GPU can handle the target resolution with the chosen model.
3. Whether to introduce the `preset` abstraction now or keep explicit `workflow_name` selection.

The orchestrator should tell the user: the next step is the Proposal phase, where we will define the exact checkpoint name, resolution, and preset contract.
