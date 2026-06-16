# Delta for Model Weight Caching

## MODIFIED Requirements

### Requirement: Realistic Persona Checkpoint Whitelist Entry

The system MUST include `RealVisXL_V4.0.safetensors` in the model whitelist for the `realistic_persona` workflow. The checkpoint MUST be pre-cached in the Modal Volume before inference. If the checkpoint is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`. If the checkpoint is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`.
(Previously: Whitelisted `juggernautXL_ragnarok.safetensors` as the default checkpoint.)

#### Scenario: Realistic persona checkpoint in whitelist and cached

- GIVEN `RealVisXL_V4.0.safetensors` is in the whitelist and exists in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Realistic persona checkpoint missing from Volume

- GIVEN the checkpoint is whitelisted but not found in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

#### Scenario: Realistic persona checkpoint not in whitelist

- GIVEN `RealVisXL_V4.0.safetensors` is NOT in the whitelist
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

## ADDED Requirements

### Requirement: FaceID Adapter Whitelist Entry

The system MUST include the IP-Adapter FaceID Plus V2 SDXL adapter model identifier in the model whitelist. The adapter MUST be pre-cached in the Modal Volume before inference. If the adapter is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: FaceID adapter in whitelist and cached

- GIVEN the FaceID Plus V2 SDXL adapter is in the whitelist and exists in the Modal Volume
- WHEN a `realistic_persona` request with a reference face is submitted
- THEN the request proceeds to Modal task spawning with FaceID conditioning available

#### Scenario: FaceID adapter missing from Volume

- GIVEN the FaceID adapter is whitelisted but not found in the Modal Volume
- WHEN a `realistic_persona` request with a reference face is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

### Requirement: ComfyUI IPAdapter Plus Node Installation

The system MUST ensure `ComfyUI_IPAdapter_plus` is installed and available on the Modal inference environment. The node installation MUST be declared in the Modal environment configuration. If the node is not available at runtime, the system MUST fail fast with a clear error.

#### Scenario: IPAdapter plus node available

- GIVEN the Modal inference environment starts
- WHEN the environment is initialized
- THEN `ComfyUI_IPAdapter_plus` nodes are available for workflow execution

#### Scenario: IPAdapter plus node missing

- GIVEN the Modal inference environment starts without `ComfyUI_IPAdapter_plus`
- WHEN a `realistic_persona` request with FaceID conditioning is submitted
- THEN the system fails fast with an execution error indicating the missing node
