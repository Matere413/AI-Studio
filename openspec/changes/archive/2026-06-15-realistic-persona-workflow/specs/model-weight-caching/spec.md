# Delta for Model Weight Caching

## ADDED Requirements

### Requirement: Realistic Persona Checkpoint Whitelist Entry

The system MUST include `moodyRealMix_zitV7.safetensors` in the model whitelist for the `realistic_persona` workflow. The checkpoint MUST be pre-cached in the Modal Volume before inference. If the checkpoint is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`. If the checkpoint is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`.

#### Scenario: Realistic persona checkpoint in whitelist and cached

- GIVEN `moodyRealMix_zitV7.safetensors` is in the whitelist and exists in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Realistic persona checkpoint missing from Volume

- GIVEN the checkpoint is whitelisted but not found in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

#### Scenario: Realistic persona checkpoint not in whitelist

- GIVEN `moodyRealMix_zitV7.safetensors` is NOT in the whitelist
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`
