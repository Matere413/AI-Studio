# Delta for Model Weight Caching

## ADDED Requirements

### Requirement: Qwen Model Whitelist Entries

The system MUST include the following model identifiers in the whitelist for the `qwen_txt2img` workflow: Qwen FP8 UNET, Qwen CLIP, Qwen VAE, and the Qwen Lightning LoRA. Each model MUST be pre-cached in the Modal Volume before inference. If any Qwen model is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`. If a whitelisted Qwen model is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: All Qwen models in whitelist and cached

- GIVEN all Qwen models (UNET, CLIP, VAE, Lightning LoRA) are in the whitelist and exist in the Modal Volume
- WHEN a `qwen_txt2img` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Qwen model not in whitelist

- GIVEN the Qwen FP8 UNET is NOT in the whitelist
- WHEN a `qwen_txt2img` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

#### Scenario: Qwen Lightning LoRA missing from Volume

- GIVEN the Lightning LoRA is whitelisted but not found in the Modal Volume
- WHEN a `qwen_txt2img` request with `quality_mode = "fast"` is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

#### Scenario: Fast mode requires Lightning LoRA validation

- GIVEN `quality_mode = "fast"` is requested
- WHEN the system validates models before spawning
- THEN the Lightning LoRA MUST be validated in addition to the base Qwen models
