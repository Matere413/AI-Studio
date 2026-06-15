# Delta for Model Weight Caching

## ADDED Requirements

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
