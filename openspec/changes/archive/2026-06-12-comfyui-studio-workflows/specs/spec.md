# Specs for comfyui-studio-workflows

## Domain: workflow-engine

# Workflow Engine Specification

## Purpose

Define how ComfyUI Studio parses workflow templates plus manifests and executes parameterized workflows without coupling API code to exported node IDs.

## Requirements

### Requirement: Parse Hybrid Template and Node Map

The system MUST load a static ComfyUI API-format template together with a manifest that maps semantic inputs to node targets. The system MUST reject a workflow when a required manifest entry, node, or field reference is missing.

#### Scenario: Template and manifest are valid

- GIVEN a stored template and matching manifest
- WHEN the workflow is loaded
- THEN the engine returns a parameterizable workflow definition

#### Scenario: Manifest references an invalid node

- GIVEN a manifest points to a missing node or field
- WHEN the workflow is loaded
- THEN the engine rejects the workflow with a validation error

### Requirement: Execute Parameterized Workflows

The system MUST apply runtime parameters through the manifest and execute the resolved workflow. The system SHALL support at least text-to-image, image-to-image, and ControlNet workflows through the same execution contract.

#### Scenario: Execute text-to-image workflow

- GIVEN a text-to-image template and valid prompt parameters
- WHEN the engine executes the workflow
- THEN ComfyUI receives a resolved graph for that template

#### Scenario: Execute image-conditional workflow

- GIVEN an image-to-image or ControlNet template and required image inputs
- WHEN the engine executes the workflow
- THEN the resolved graph includes the referenced image-conditioned parameters

## Domain: model-weight-caching

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

## Domain: image-generation

# Delta for image-generation

## MODIFIED Requirements

### Requirement: Accept Generation Requests

The system MUST expose `POST /generate` and accept `application/json` with required `prompt` plus optional workflow-selection parameters for `checkpoint`, `lora`, and other declared generation inputs. The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

(Previously: `POST /generate` accepted only a prompt for one hardcoded txt2img workflow.)

#### Scenario: Dynamic generation request accepted

- GIVEN a client sends a valid prompt and supported generation parameters
- WHEN `POST /generate` is called
- THEN the request is accepted for the selected generation workflow

#### Scenario: Unsupported generation parameter rejected

- GIVEN a client sends a parameter not declared by the selected workflow
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error
