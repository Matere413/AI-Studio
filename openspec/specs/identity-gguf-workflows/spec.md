# Identity GGUF Workflows Specification

## Purpose

Define the contract for Flux GGUF-based identity-preserving generation using PuLID conditioning and Impact Pack FaceDetailer enhancement.

## Requirements

### Requirement: Accept Identity GGUF Workflow Requests

The system MUST accept `POST /generate` requests with `workflow = "identidad_gguf"` and parameters: `prompt` (required, non-empty string), `image_url` (required, valid URL to reference identity image), `width` (optional integer, multiple of 64, default from manifest), `height` (optional integer, multiple of 64, default from manifest), and `seed` (optional integer, -1 for random). The system MUST return `202 Accepted` with `job_id` and `status = "pending"`.

#### Scenario: Identity GGUF request accepted

- GIVEN a client sends `workflow = "identidad_gguf"` with `prompt` and `image_url`
- WHEN `POST /generate` is called
- THEN the request is accepted with `202` and a `job_id`

#### Scenario: Missing reference image rejected

- GIVEN a client sends `workflow = "identidad_gguf"` without `image_url`
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error

#### Scenario: Invalid image_url format rejected

- GIVEN a client sends `image_url` that is not a valid URL
- WHEN `POST /generate` is called
- THEN the request is rejected with a validation error for `image_url`

### Requirement: Load Identity GGUF Workflow Manifest

The system MUST load the `identidad_gguf` workflow template and manifest from `api/src/workflows/identidad_gguf/`. The manifest MUST declare `prompt` (required), `image_url` (required), `width` (optional), `height` (optional), and `seed` (optional) as supported parameters. The engine MUST validate that the manifest's referenced GGUF UNET, CLIP, PuLID, and face detector models are in the approved whitelist before loading.

#### Scenario: Identity GGUF workflow loads

- GIVEN the `identidad_gguf` directory contains a valid template and manifest
- WHEN the workflow engine loads the `identidad_gguf` workflow
- THEN the engine returns a parameterizable definition with all declared parameters

#### Scenario: Identity GGUF manifest references non-whitelisted model

- GIVEN the `identidad_gguf` manifest references a GGUF UNET not in the whitelist
- WHEN the workflow engine loads the manifest
- THEN the engine rejects with a validation error

### Requirement: Resolve Identity GGUF Parameters

The system MUST resolve `image_url` to a runtime-downloadable reference image and inject it into the workflow's `LoadImage` node (or equivalent image-input node) at execution time. The system MUST resolve `width` and `height` from the request, falling back to manifest defaults. The system MUST resolve `seed` to an integer, generating a random seed when `-1` or omitted.

#### Scenario: Reference image injected into workflow

- GIVEN an `identidad_gguf` request with a valid `image_url`
- WHEN the engine resolves parameters
- THEN the ComfyUI graph's image-input node receives the downloaded reference image

#### Scenario: Default dimensions applied

- GIVEN an `identidad_gguf` request without `width` or `height`
- WHEN the engine resolves parameters
- THEN the engine applies default dimensions from the manifest

### Requirement: GGUF Identity Generation Execution

The system MUST execute the `identidad_gguf` workflow on Modal GPU with the following pipeline: (1) load Flux GGUF UNET and CLIP, (2) apply PuLID identity conditioning from the reference image, (3) generate the image from the prompt, (4) apply FaceDetailer enhancement via Impact Pack. The system MUST route this workflow through the existing `run_generation_heavy` function. The system MUST enforce the standard 300-second hard timeout.

#### Scenario: Identity GGUF generation completes

- GIVEN a valid `identidad_gguf` request is submitted
- WHEN the heavy Modal function executes
- THEN the workflow completes with an identity-preserved, face-enhanced image

#### Scenario: FaceDetailer enhancement applied

- GIVEN the generation step produces an image
- WHEN the FaceDetailer node executes
- THEN the output image has enhanced facial details

### Requirement: Identity GGUF Checkpoint Whitelist Entry

The system MUST include `flux1-dev-q4_k_m.gguf` in the model whitelist. The GGUF UNET, `t5xxl_fp8_e4m3fn.safetensors` CLIP, `pulid_flux_v0.9.1.safetensors` PuLID model, and `face_yolov8m.onnx` face detector MUST all be whitelisted and pre-cached in the Modal Volume. If any required model is NOT in the whitelist, the system MUST return HTTP 400 with `error.code = "model_not_allowed"`. If a whitelisted model is missing from the Volume, the system MUST return HTTP 500 with `error.code = "model_not_cached"`.

#### Scenario: All GGUF models in whitelist and cached

- GIVEN all required GGUF/PuLID/Impact models are in the whitelist and exist in the Modal Volume
- WHEN an `identidad_gguf` request is submitted
- THEN the request proceeds to Modal task spawning

#### Scenario: GGUF UNET not in whitelist

- GIVEN `flux1-dev-q4_k_m.gguf` is NOT in the whitelist
- WHEN an `identidad_gguf` request is submitted
- THEN the server returns HTTP 400 with `error.code = "model_not_allowed"`

#### Scenario: PuLID model missing from Volume

- GIVEN `pulid_flux_v0.9.1.safetensors` is whitelisted but not found in the Modal Volume
- WHEN an `identidad_gguf` request is submitted
- THEN the server returns HTTP 500 with `error.code = "model_not_cached"`

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
