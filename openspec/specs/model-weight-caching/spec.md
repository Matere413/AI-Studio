# Model Weight Caching Specification

## Purpose

Define runtime acquisition and reuse of `.safetensors` weights stored in the Modal volume.

## Requirements

### Requirement: Download and Reuse Safetensors Weights

The system MUST NOT download models at runtime in V1. All models MUST be pre-cached in the Modal Volume. The system MUST reuse an existing cached file on later requests for the same model identifier. Runtime downloads are deferred to V2.
(Previously: The system would download a requested `.safetensors` file into the Modal volume when not already cached.)

#### Scenario: Cache hit skips download

- GIVEN a requested model already exists in the Modal Volume
- WHEN the cache service resolves the model
- THEN the existing file path is returned without downloading

#### Scenario: Cache miss rejected in V1

- GIVEN a requested model is absent from the Modal Volume
- WHEN the cache service attempts to resolve the model
- THEN the request fails with `model_not_cached` error (no download attempted)

### Requirement: Enforce Model Whitelist

The system MUST maintain a pre-approved whitelist of allowed model identifiers. Before spawning any Modal inference task, the system MUST validate the requested `checkpoint` (and any `lora`) against this whitelist. Requests referencing models not in the whitelist MUST be rejected immediately with HTTP 400 and `{"error": {"code": "model_not_allowed", "detail": "Model '{model_id}' is not in the allowed whitelist."}}`. The whitelist MUST be configurable via environment variable or configuration file.

#### Scenario: Whitelisted model accepted

- GIVEN a request specifies a checkpoint that exists in the whitelist
- WHEN `POST /generate` is called
- THEN the request proceeds to Modal task spawning

#### Scenario: Non-whitelisted model rejected

- GIVEN a request specifies a checkpoint NOT in the whitelist
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`
- AND no Modal task is spawned

#### Scenario: Multiple models all validated

- GIVEN a request specifies both a checkpoint and a lora
- WHEN both models are in the whitelist
- THEN the request proceeds to Modal task spawning

#### Scenario: One of multiple models not whitelisted

- GIVEN a request specifies a whitelisted checkpoint but a non-whitelisted lora
- WHEN `POST /generate` is called
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"` referencing the non-whitelisted lora
- AND no Modal task is spawned

### Requirement: Pre-Cached Models Only (V1 Boundary)

The system MUST NOT perform runtime model downloads. All whitelisted models MUST already be cached in the Modal Volume before inference. If a whitelisted model identifier is not found in the Volume, the system MUST return HTTP 500 with `{"error": {"code": "model_not_cached", "detail": "..."}}`. This is a V1 constraint; runtime downloads are deferred to V2.

#### Scenario: Whitelisted model exists in Volume

- GIVEN a whitelisted model identifier
- WHEN the model file exists in the Modal Volume
- THEN inference proceeds normally

#### Scenario: Whitelisted model missing from Volume

- GIVEN a whitelisted model identifier
- WHEN the model file does NOT exist in the Modal Volume
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

### Requirement: Flux 2 Model Whitelist Entries

The system MUST include the following model identifiers in the whitelist for Flux 2 workflows: `flux2_dev_fp8mixed.safetensors` (base UNET), `mistral_3_small_flux2_bf16.safetensors` (text encoder), `full_encoder_small_decoder.safetensors` (VAE), and `Flux_2-Turbo-LoRA_comfyui.safetensors` (Turbo LoRA). Each model MUST be pre-cached in the Modal Volume. If any Flux 2 model is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`. If a whitelisted Flux 2 model is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: All Flux 2 models in whitelist and cached

- GIVEN all Flux 2 models are in the whitelist and exist in the Modal Volume
- WHEN a `flux2_txt2img` or `flux2_editing` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Flux 2 model not in whitelist

- GIVEN `flux2_dev_fp8mixed.safetensors` is NOT in the whitelist
- WHEN a Flux 2 request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

#### Scenario: Turbo LoRA missing from Volume

- GIVEN the Turbo LoRA is whitelisted but not found in the Modal Volume
- WHEN `use_turbo = true` and a Flux 2 request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

<!-- Requirements removed in refactor-flux-api:
  - Premium Checkpoint Whitelist Entry → retired, product_premium workflow removed
  - Realistic Persona Checkpoint Whitelist Entry → retired, realistic_persona workflow removed
  - FaceID Adapter Whitelist Entry → retired, tied to realistic_persona FaceID conditioning
  - ComfyUI IPAdapter Plus Node Installation → retired, tied to realistic_persona
  - Qwen Model Whitelist Entries → retired, qwen_txt2img workflow removed
-->

### Requirement: Atomic flow model whitelist

The whitelist MUST include BRIA extraction, FLUX Depth/Canny ControlNet, FLUX base checkpoint, and PuLID FLUX models.

#### Scenario: Required atomic models cached

- GIVEN all atomic flow models are whitelisted and present in the Modal volume
- WHEN a flow request is submitted
- THEN it proceeds to spawn

<!-- Requirement removed in sdd-2-modal-flows: Identity GGUF Checkpoint Whitelist Entry
  (Reason: replaced by PuLID + FLUX identity flow.)
  (Migration: remove `flux1-dev-q4_k_m.gguf` and GGUF custom nodes; update tests and docs to reference Flow 3.)
-->

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
