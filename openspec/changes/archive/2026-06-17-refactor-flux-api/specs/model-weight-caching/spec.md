# Delta for Model Weight Caching

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Premium Checkpoint Whitelist Entry

(Reason: `product_premium` workflow is retired.)
(Migration: None.)

### Requirement: Realistic Persona Checkpoint Whitelist Entry

(Reason: `realistic_persona` workflow is retired.)
(Migration: None.)

### Requirement: FaceID Adapter Whitelist Entry

(Reason: IP-Adapter FaceID Plus V2 SDXL was for `realistic_persona` which is retired.)
(Migration: Flux 2 identity uses PuLID from `identidad_gguf` models.)

### Requirement: ComfyUI IPAdapter Plus Node Installation

(Reason: Tied to `realistic_persona` FaceID conditioning which is retired.)
(Migration: None.)

### Requirement: Qwen Model Whitelist Entries

(Reason: `qwen_txt2img` workflow is retired.)
(Migration: None.)
