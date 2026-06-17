# Delta for Model Weight Caching

## ADDED Requirements

### Requirement: Identity GGUF Checkpoint Whitelist Entry

The system MUST include `flux1-dev-q4_k_m.gguf` in the model whitelist. The GGUF UNET, `t5xxl_fp8_e4m3fn.safetensors` CLIP, `pulid_flux_v0.9.1.safetensors` PuLID model, and `face_yolov8m.onnx` face detector MUST all be whitelisted and pre-cached in the Modal Volume. If any required model is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`. If a whitelisted model is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: All GGUF models in whitelist and cached

- GIVEN all required GGUF/PuLID/Impact models are in the whitelist and exist in the Modal Volume
- WHEN an `identidad_gguf` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: GGUF UNET not in whitelist

- GIVEN `flux1-dev-q4_k_m.gguf` is NOT in the whitelist
- WHEN an `identidad_gguf` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

#### Scenario: PuLID model missing from Volume

- GIVEN `pulid_flux_v0.9.1.safetensors` is whitelisted but not found in the Modal Volume
- WHEN an `identidad_gguf` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

### Requirement: GGUF Custom Node Installation

The system MUST ensure the following custom nodes are installed and available on the Modal inference environment: `ComfyUI-GGUF`, PuLID Flux wrapper, and `ComfyUI-Impact-Pack`. The node installations MUST be declared in the Modal environment configuration (`modal_config.py`). If any required node is not available at runtime, the system MUST fail fast with a clear error indicating the missing node.

#### Scenario: All GGUF custom nodes available

- GIVEN the Modal inference environment starts
- WHEN the environment is initialized
- THEN `ComfyUI-GGUF`, PuLID Flux, and `ComfyUI-Impact-Pack` nodes are available

#### Scenario: Missing GGUF node causes fast failure

- GIVEN the Modal inference environment starts without `ComfyUI-GGUF`
- WHEN an `identidad_gguf` request is submitted
- THEN the system fails fast with an execution error indicating the missing node
