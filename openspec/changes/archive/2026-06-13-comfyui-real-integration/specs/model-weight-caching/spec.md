# Delta for model-weight-caching

## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Fail Safely on Invalid Downloads

(Reason: Runtime downloads are not performed in V1; all models must be pre-cached. This requirement is superseded by the pre-cached-only boundary.)
(Migration: Tests for download failure should be replaced with tests for `model_not_cached` error when a whitelisted model is missing from the Volume.)
