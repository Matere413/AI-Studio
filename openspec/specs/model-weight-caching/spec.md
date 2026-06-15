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

### Requirement: Premium Checkpoint Whitelist Entry

The system MUST include the premium checkpoint identifier for the `product_premium` workflow in the model whitelist. The premium checkpoint MUST be pre-cached in the Modal Volume before inference. If the premium checkpoint is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: Premium checkpoint in whitelist and cached

- GIVEN the premium checkpoint is in the whitelist and exists in the Modal Volume
- WHEN a `product_premium` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Premium checkpoint missing from Volume

- GIVEN the premium checkpoint is whitelisted but not found in the Modal Volume
- WHEN a `product_premium` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

#### Scenario: Premium checkpoint not in whitelist

- GIVEN the premium checkpoint is NOT in the whitelist
- WHEN a `product_premium` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

### Requirement: Realistic Persona Checkpoint Whitelist Entry

The system MUST include `juggernautXL_ragnarok.safetensors` in the model whitelist for the `realistic_persona` workflow. The checkpoint MUST be pre-cached in the Modal Volume before inference. If the checkpoint is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`. If the checkpoint is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`.

#### Scenario: Realistic persona checkpoint in whitelist and cached

- GIVEN `juggernautXL_ragnarok.safetensors` is in the whitelist and exists in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: Realistic persona checkpoint missing from Volume

- GIVEN the checkpoint is whitelisted but not found in the Modal Volume
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

#### Scenario: Realistic persona checkpoint not in whitelist

- GIVEN `juggernautXL_ragnarok.safetensors` is NOT in the whitelist
- WHEN a `realistic_persona` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`
