## Exploration: Qwen Text-to-Image Pipeline Integration

### Current State

The ai-studio backend uses a hexagonal architecture with a `WorkflowEngine` that pairs a ComfyUI JSON template (`workflow.json`) with a YAML manifest (`manifest.yaml`) under `api/src/workflows/{workflow_name}/`. The engine validates manifest references, applies runtime parameters, and returns a resolved graph for Modal GPU execution.

Current workflows:
- `txt2img` — standard CheckpointLoaderSimple + KSampler pipeline
- `img2img` — similar but with denoise and image_url inputs
- `controlnet` — ControlNet-guided generation
- `product_premium` — locked-format workflow with dimension presets
- `realistic_persona` — identity-preservation workflow with IP-Adapter

The `GenerateRequest` model defines `WorkflowName` as a Literal of allowed workflow names. The `GenerationService` resolves workflows, validates models against a whitelist (`ALLOWED_MODELS_JSON`), checks cache presence in the Modal Volume, and spawns `run_generation` on Modal GPU.

### The Qwen Workflow JSON

The provided workflow (`image_qwen_Image_2512.json`) is a text-to-image pipeline with these characteristics:

**Architecture:**
- `UNETLoader` loads `qwen_image_2512_fp8_e4m3fn.safetensors`
- `CLIPLoader` loads `qwen_2.5_vl_7b_fp8_scaled.safetensors` (type: `qwen_image`)
- `VAELoader` loads `qwen_image_vae.safetensors`
- `ModelSamplingAuraFlow` applies shift=3.1
- `EmptySD3LatentImage` at 1328×1328
- `KSampler` with euler/simple, denoise=1.0

**Smart Switching (Lightning LoRA mode):**
- A `PrimitiveBoolean` (`238:229`) toggles between standard mode (50 steps, CFG=4.0, base UNET) and Lightning mode (4 steps, CFG=1.0, LoRA-loaded model)
- `ComfySwitchNode` nodes route `steps`, `cfg`, and `model` inputs dynamically
- Lightning LoRA: `Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors` via `LoraLoaderModelOnly`

**Key Issues:**
1. The JSON is **flat** (no `"prompt"` wrapper), unlike existing templates which wrap nodes under `"prompt"`
2. Uses **custom nodes** (`ComfySwitchNode`, `PrimitiveBoolean`, `PrimitiveInt`, `PrimitiveFloat`) not present in current workflows
3. Node IDs use colons (`238:XXX`) — valid but unusual
4. The prompt/negative prompt are hardcoded in the JSON

### Affected Areas

- `api/src/workflows/` — new `qwen_txt2img/` directory with template + manifest
- `api/src/features/generation/models.py` — add `qwen_txt2img` to `WorkflowName` literal
- `api/src/features/generation/service.py` — may need parameter handling for Lightning toggle
- `api/src/shared/workflows/engine.py` — flat JSON vs `"prompt"`-wrapped template handling
- `api/src/shared/workflows/cache.py` — whitelist must include Qwen model filenames
- Modal infrastructure — Qwen models must be pre-cached in the Modal Volume

### Approaches

#### 1. Simplified Workflow Template (Recommended)
Strip the switch nodes and custom primitives from the Qwen JSON, producing a clean standard ComfyUI graph wrapped in `"prompt"`. Expose Lightning mode as a separate workflow (`qwen_txt2img_lightning`) or as a boolean API parameter that the service layer translates into different default values.

- **Pros:**
  - Uses only standard ComfyUI nodes (no custom node installation required)
  - Follows the existing template+manifest pattern exactly
  - Manifest maps directly to KSampler/CLIPTextEncode inputs
  - Low cognitive overhead for reviewers
- **Cons:**
  - Diverges from the user-provided JSON (we modify rather than use as-is)
  - Two workflows if we split standard vs Lightning
- **Effort:** Low

#### 2. Use JSON As-Is with Engine Extension
Keep the original Qwen JSON structure, add a `"prompt"` wrapper during template loading, create a manifest that maps to the custom primitive and switch nodes, and require `ComfySwitchNode` + primitive nodes to be installed in the ComfyUI environment.

- **Pros:**
  - Preserves the user's exact workflow logic
  - Single workflow handles both standard and Lightning modes
- **Cons:**
  - Adds custom node dependencies to the ComfyUI server image
  - Manifest mapping is indirect (parameters go into switch primitives, not KSampler directly)
  - More complex to test and debug
  - `WorkflowEngine` may need changes to support flat templates
- **Effort:** Medium

#### 3. Native Service-Level Switching
Bypass the generic `WorkflowEngine` for Qwen. Build a dedicated service that constructs the ComfyUI graph programmatically, handling the Lightning toggle in Python before spawning Modal work.

- **Pros:**
  - Maximum flexibility
  - No template/manifest maintenance
- **Cons:**
  - Breaks the hexagonal workflow abstraction
  - Duplicates graph construction logic
  - Harder to maintain and version
- **Effort:** High

### Recommendation

**Approach 1: Simplified Workflow Template.**

Create a clean Qwen txt2img workflow by:
1. Removing all `ComfySwitchNode`, `PrimitiveBoolean`, `PrimitiveInt`, and `PrimitiveFloat` nodes
2. Connecting `KSampler` inputs directly to standard values or manifest-mapped parameters
3. Wrapping the graph in `"prompt"` to match existing template format
4. Optionally creating `qwen_txt2img_lightning/` as a separate 4-step workflow, OR adding a `lightning: bool` field to `GenerateRequest` that the service layer uses to select defaults (but still resolves to a single simplified graph)

This keeps the backend simple, avoids custom node dependencies, and follows established patterns. The frontend can still present a "Lightning mode" toggle by passing `workflow_name=qwen_txt2img_lightning` or `lightning=true`.

### Risks

- **Model Caching:** Qwen model files (`qwen_image_2512_fp8_e4m3fn.safetensors`, `qwen_2.5_vl_7b_fp8_scaled.safetensors`, `qwen_image_vae.safetensors`, and the Lightning LoRA) are large and must be pre-cached in the Modal Volume. Missing models will raise `model_not_cached` errors.
- **Custom Node Dependency (if Approach 2):** `ComfySwitchNode` and primitive nodes must be installed in the ComfyUI Docker image. If missing, ComfyUI will fail at execution time.
- **Template Format Mismatch:** The flat JSON structure requires either wrapping or engine modification. If overlooked, `_load_graph_from_dict` in `modal_tasks.py` will reject the graph.
- **VRAM Requirements:** Qwen 2512 at 1328×1328 with FP8 may require significant VRAM. Modal GPU selection (currently T4) should be verified.
- **Whitelist Maintenance:** New model filenames must be added to `ALLOWED_MODELS_JSON` environment variable / whitelist.

### Ready for Proposal

**Yes.** The orchestrator should tell the user:

> "The Qwen workflow can be integrated cleanly by creating a new `qwen_txt2img` workflow template. However, the provided JSON uses custom switch nodes and a flat structure that doesn't match our existing engine. We recommend **simplifying the workflow** to standard ComfyUI nodes — this removes custom node dependencies and keeps the backend maintainable. 
>
> **Open question:** Should Lightning LoRA mode be a separate workflow (`qwen_txt2img_lightning`) or a boolean parameter on the same endpoint?"
