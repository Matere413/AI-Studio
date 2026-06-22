# SDD-2 Modal Flows — Specification

## 1. BaseAtomicFlow & ImageArtifact Contract

### ADDED Requirement: BaseAtomicFlow typed contract

The system MUST define `BaseAtomicFlow` as a Pydantic v2 base model with fields `workflow_name`, `gpu_profile`, `timeout_s`, and `prompt`. Each concrete flow SHALL subclass it, bind a unique `workflow_name`, and register in the flow registry.

#### Scenario: Valid flow subclass registers

- GIVEN an `ExtractionFlow` subclass declaring `workflow_name = "extraction"`
- WHEN the flow registry loads
- THEN the flow is exposed under `"extraction"`

#### Scenario: Missing workflow_name rejected

- GIVEN a subclass omits `workflow_name`
- WHEN the model is validated
- THEN Pydantic raises a validation error

#### Scenario: Prompt length enforced

- GIVEN a request with `prompt` longer than 4000 characters
- WHEN validated
- THEN the request is rejected

### ADDED Requirement: ImageArtifact handoff

The system MUST define `ImageArtifact` with `volume_path`, `media_type`, `source_job_id`, `width`, and `height`. It SHALL accept `volume_path`, `url`, or `upload` sources, but `volume_path` MUST be the primary handoff path between flows. The system MUST validate that `volume_path` stays within the job volume root and that `media_type` is `image/png` or `image/jpeg`.

#### Scenario: Prior flow output feeds next flow

- GIVEN a composition request referencing an extraction output artifact by `volume_path`
- WHEN the composition flow executes
- THEN it reads the PNG from the validated volume path

#### Scenario: Artifact path escape rejected

- GIVEN an artifact with `volume_path = "../../../etc/passwd"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_artifact"`

#### Scenario: Unsupported media type rejected

- GIVEN an artifact with `media_type = "image/webp"`
- WHEN validated
- THEN the system rejects with `error.code = "invalid_media_type"`

### ADDED Requirement: FlowOutput contract

The system MUST return `FlowOutput` containing `job_id` and `artifacts: list[ImageArtifact]`. Every successful flow execution MUST emit at least one artifact.

#### Scenario: Successful flow returns artifacts

- GIVEN a flow completes without errors
- WHEN the response is built
- THEN `FlowOutput.artifacts` contains one or more valid `ImageArtifact` entries

### ADDED Requirement: Typed flow dispatch

The system MUST route requests through per-flow Pydantic v2 models and MUST NOT extend the monolithic `GenerateRequest` for new atomic flows.

#### Scenario: Typed request accepted

- GIVEN `POST /generate/extraction` with a valid `ExtractionRequest`
- WHEN validated
- THEN the job is accepted and routed to the extraction flow

#### Scenario: Monolithic field rejected

- GIVEN a typed flow request contains a field from `GenerateRequest` not in its schema
- WHEN validated
- THEN the request is rejected with a validation error

## 2. Flow 1: Extraction (BRIA)

### ADDED Requirement: Extraction inputs

The extraction flow MUST accept `input_image: ImageArtifact` and an optional `mask_margin`. It MUST produce a transparent PNG `ImageArtifact` declared in the manifest `outputs.artifacts`.

#### Scenario: Valid source image produces mask

- GIVEN a source image containing a foreground subject
- WHEN the BRIA extraction workflow runs
- THEN a transparent PNG is saved to the volume and returned as an artifact

#### Scenario: Missing source rejected

- GIVEN an extraction request without `input_image`
- WHEN validated
- THEN the request is rejected

#### Scenario: Invalid source media type rejected

- GIVEN `input_image.media_type = "image/webp"`
- WHEN validated
- THEN the request is rejected

### ADDED Requirement: Extraction pipeline

The system MUST execute a ComfyUI graph matching `LoadImage → BriaRMBG → SaveImage`. The output MUST be an RGBA PNG with alpha channel. The flow SHALL run on `gpu_profile = L4` or higher with `timeout_s = 300`.

#### Scenario: Complex edges handled

- GIVEN a subject with fine hair or fur against a busy background
- WHEN BRIA runs
- THEN the alpha channel preserves edge detail without background halos

#### Scenario: Missing BRIA node fails fast

- GIVEN the `ComfyUI-BRIA_AI-RMBG` node is not installed
- WHEN the flow spawns
- THEN it fails with `error.code = "node_missing"`

### ADDED Requirement: Extraction outputs

The manifest MUST declare an output artifact named `extracted_image` with `media_type = "image/png"` and `has_alpha = true`.

## 3. Flow 2: Composition (FLUX + ControlNet)

### ADDED Requirement: Composition inputs

The composition flow MUST accept `prompt`, `background_image: ImageArtifact`, `foreground_image: ImageArtifact`, `control_mode ∈ {"depth", "canny"}`, optional `control_strength` (0.0–2.0, default 1.0), and optional `seed`.

#### Scenario: Extraction output feeds composition

- GIVEN a valid transparent PNG artifact from the extraction flow
- WHEN composition runs with `control_mode = "depth"`
- THEN the foreground subject is composed onto a generated background matching depth guidance

#### Scenario: Explicit upload feeds composition

- GIVEN a user-uploaded foreground and background image
- WHEN composition runs with `control_mode = "canny"`
- THEN the output respects the uploaded foreground and canny edge guidance

#### Scenario: Invalid control_mode rejected

- GIVEN `control_mode = "pose"`
- WHEN validated
- THEN the request is rejected

### ADDED Requirement: Composition pipeline

The system MUST execute a FLUX + ControlNet graph: preprocess the background, apply ControlNet conditioning, encode the foreground via VAE, sample with FLUX UNet, decode, and save. The flow SHALL run on `gpu_profile = L4` or higher with `timeout_s = 600`.

#### Scenario: Depth mode produces coherent scene

- GIVEN valid background, foreground, and `control_mode = "depth"`
- WHEN the workflow runs
- THEN the generated image places the foreground at a depth consistent with the background

#### Scenario: ControlNet model missing fails fast

- GIVEN the requested ControlNet model is not cached
- WHEN the flow spawns
- THEN it fails with `error.code = "model_not_cached"`

#### Scenario: VRAM pressure handled

- GIVEN the L4 profile exhausts VRAM during sampling
- WHEN the error is caught
- THEN the system returns `error.code = "gpu_oom"` and retries are not attempted automatically

### ADDED Requirement: Composition outputs

The flow MUST return a composed image `ImageArtifact` with `media_type = "image/png"` and dimensions matching the requested or default resolution.

## 4. Flow 3: Identity (PuLID + FLUX)

### ADDED Requirement: Identity inputs

The identity flow MUST accept `prompt`, `reference_face: ImageArtifact`, optional `seed`, and optional `width`/`height` that are multiples of 64.

#### Scenario: Valid identity request

- GIVEN a front-facing identity reference artifact
- WHEN the PuLID + FLUX workflow runs
- THEN the generated image preserves the subject's identity

#### Scenario: Non-face reference rejected

- GIVEN a reference image with no detectable face
- WHEN the face detector runs
- THEN the flow fails with `error.code = "no_face_detected"`

#### Scenario: Invalid resolution rejected

- GIVEN `width = 1000` (not a multiple of 64)
- WHEN validated
- THEN the request is rejected

### ADDED Requirement: Identity pipeline

The system MUST execute a PuLID + FLUX graph: `LoadImage(face) → PuLIDModelLoader → ApplyPuLID → CLIPTextEncode → KSampler(FLUX UNet) → VAEDecode → SaveImage`. The flow SHALL default to `gpu_profile = A100` with `timeout_s = 1200`, and MAY fall back to `L4` with fp8 optimization when A100 is unavailable.

#### Scenario: Identity preserved across prompts

- GIVEN the same reference face and two different prompts
- WHEN both workflows complete
- THEN the generated faces are recognizably the same person

#### Scenario: PuLID model not whitelisted

- GIVEN the PuLID model is absent from the whitelist
- WHEN the request is validated
- THEN it is rejected with `error.code = "model_not_allowed"`

#### Scenario: Missing PuLID node fails fast

- GIVEN the `ComfyUI-PuLID-Flux` node is not installed
- WHEN the flow spawns
- THEN it fails with `error.code = "node_missing"`

### ADDED Requirement: Identity output

The flow MUST return a generated image `ImageArtifact` with `media_type = "image/png"` and dimensions that are multiples of 64.

## 5. Workflow Engine Delta

### ADDED Requirement: Atomic flow contract

The engine MUST load a `BaseAtomicFlow` manifest that declares `outputs.artifacts` alongside `inputs`.

#### Scenario: Manifest declares output artifact

- GIVEN a flow manifest with `outputs.artifacts = [{name, media_type}]`
- WHEN loaded
- THEN the engine exposes output artifact metadata to callers

### MODIFIED Requirement: Execute Parameterized Workflows

The engine MUST support `flux2_txt2img`, `flux2_editing`, and registered atomic flows through the same execution contract.
(Previously: supported only legacy workflows including `identidad_gguf`.)

#### Scenario: Atomic flow execution

- GIVEN a registered composition flow and valid request
- WHEN executed
- THEN the engine resolves inputs, runs ComfyUI, and maps output files to artifacts

## 6. Image Generation Delta

### ADDED Requirement: Typed flow endpoints

The system MUST expose `POST /generate/extraction`, `POST /generate/composition`, and `POST /generate/identity` accepting the per-flow Pydantic request and returning `202 Accepted` with `job_id` and `status = pending`.

#### Scenario: New flow endpoint accepts request

- GIVEN `POST /generate/identity` with a valid `IdentityRequest`
- WHEN called
- THEN the response contains `job_id` and `status = pending`

### MODIFIED Requirement: Legacy GenerateRequest

`POST /generate` MUST continue to accept `flux2_txt2img`, `flux2_editing`, and `identidad_gguf` during rollout. It SHALL NOT be extended for new atomic flows.
(Previously: supported only the three workflows listed above.)

## 7. Model Weight Caching Delta

### ADDED Requirement: Atomic flow model whitelist

The whitelist MUST include BRIA extraction, FLUX Depth/Canny ControlNet, FLUX base checkpoint, and PuLID FLUX models.

#### Scenario: Required atomic models cached

- GIVEN all atomic flow models are whitelisted and present in the Modal volume
- WHEN a flow request is submitted
- THEN it proceeds to spawn

### REMOVED Requirement: Identity GGUF Checkpoint Whitelist Entry

(Reason: replaced by PuLID + FLUX identity flow.)
(Migration: remove `flux1-dev-q4_k_m.gguf` and GGUF custom nodes; update tests and docs to reference Flow 3.)

## 8. Identity GGUF Workflows Delta

### REMOVED Requirement: All Identity GGUF Requirements

(Reason: `identidad_gguf` is deprecated and replaced by Flow 3.)
(Migration: route callers to `POST /generate/identity`; remove `api/src/workflows/identidad_gguf/` after rollout.)
