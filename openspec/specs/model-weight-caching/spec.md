# Model Weight Caching Specification

## Purpose

Define runtime acquisition and reuse of `.safetensors` weights stored in the Modal volume.

## Requirements

### Requirement: Download and Reuse Safetensors Weights

The system MUST download a requested `.safetensors` file into the configured Modal volume when the file is not already cached. The system MUST reuse an existing cached file on later requests for the same model identifier.

#### Scenario: Cache miss downloads model

- GIVEN a requested model is absent from the Modal volume
- WHEN the cache service resolves the model
- THEN the service downloads the `.safetensors` file and returns its stored path

#### Scenario: Cache hit skips download

- GIVEN a requested model already exists in the Modal volume
- WHEN the cache service resolves the model
- THEN the existing file path is returned without re-downloading

### Requirement: Fail Safely on Invalid Downloads

The system SHALL mark a model request as failed when the download cannot complete or validate, and it MUST NOT report the model as cached.

#### Scenario: Download fails

- GIVEN a model URL is unreachable or invalid
- WHEN the cache service attempts the download
- THEN the request fails with a retriable cache error
