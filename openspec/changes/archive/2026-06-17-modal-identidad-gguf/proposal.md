# Proposal: Modal Identidad GGUF Workflow

## Intent

Enable the downloaded `identidad_gguf.json` ComfyUI workflow to run on the Modal backend, preserving identity with Flux GGUF + PuLID and improving faces with Impact Pack. This removes the gap where local ComfyUI workflows using custom nodes cannot execute in production Modal images.

## Scope

### In Scope
- Add an `identidad_gguf` workflow template and manifest from `/Users/matere/Downloads/identidad_gguf.json`.
- Install required Modal custom nodes: `ComfyUI-GGUF`, PuLID Flux nodes, and `ComfyUI-Impact-Pack`.
- Whitelist and validate required cached models for GGUF UNET, CLIP, PuLID, and face detector assets.
- Route `workflow = "identidad_gguf"` through heavy Modal generation with existing WebSocket/output behavior.

### Out of Scope
- Runtime model downloads; all models remain pre-cached in Modal Volume.
- Training/fine-tuning identity models.
- Replacing existing `realistic_persona` IP-Adapter behavior.

## Capabilities

### New Capabilities
- `identity-gguf-workflows`: Flux GGUF identity-preserving generation using PuLID and FaceDetailer.

### Modified Capabilities
- `image-generation`: accept and route `identidad_gguf` requests.
- `workflow-engine`: load and parameterize the new workflow manifest/template.
- `model-weight-caching`: validate GGUF/PuLID/Impact required cached assets and custom-node availability.

## Approach

Normalize the downloaded workflow into existing API format (`{"prompt": ...}`), store it under `api/src/workflows/identidad_gguf/`, and create a manifest for prompt, reference image, dimensions, seed, and model names. Extend request/service routing and send this workflow to `run_generation_heavy`. Update `modal_config.py` image build commands to clone/install the required custom nodes and Python deps.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/src/shared/modal_config.py` | Modified | Install custom nodes/dependencies; extend whitelist defaults. |
| `api/src/features/generation/{models.py,service.py}` | Modified | Add workflow enum, validation, routing, model checks. |
| `api/src/features/generation/modal_tasks.py` | Modified | Ensure heavy execution supports this graph timeout/GPU needs. |
| `api/src/workflows/identidad_gguf/` | New | Workflow template and manifest. |
| `api/src/tests/` | Modified | Add contract/unit coverage. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missing custom node or model path breaks boot | Med | Validate installed nodes/models before spawn; clear error. |
| L4 timeout/VRAM insufficient | Med | Use heavy route; tune defaults or document A100 fallback. |
| Workflow contains unsafe hardcoded local image | High | Replace `LoadImage` with supported runtime reference input. |

## Rollback Plan

Remove `identidad_gguf` routing, workflow files, whitelist entries, and custom-node install commands; redeploy the previous Modal image so existing workflows continue unchanged.

## Dependencies

- Cached models: `flux1-dev-q4_k_m.gguf`, `t5xxl_fp8_e4m3fn.safetensors`, `pulid_flux_v0.9.1.safetensors`, `face_yolov8m.onnx`.
- Custom nodes: `ComfyUI-GGUF`, PuLID Flux wrapper, `ComfyUI-Impact-Pack`.

## Success Criteria

- [ ] `POST /generate` accepts `workflow = "identidad_gguf"` with prompt and reference image.
- [ ] Modal image boots with all required custom nodes available.
- [ ] Completed jobs return an image through existing WebSocket and `/images/{job_id}` flow.
