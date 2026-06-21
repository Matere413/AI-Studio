# Tasks: SDD-2 Modal Flows

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1050–1200 (3 PRs) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 (stacked to main) |
| Delivery strategy | ask-always |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation types + Extraction flow + dispatch | PR 1 | ~340 lines; base contracts, modal config, extraction workflow+flow, service dispatch, routes for extraction, tests |
| 2 | Composition flow (FLUX + ControlNet) | PR 2 | ~225 lines; independent flow module, workflow graph, route, tests |
| 3 | Identity flow + legacy GGUF removal | PR 3 | ~500 lines; identity flow, route, service cleanup, models.py deprecation, delete `identidad_gguf/`, tests |

## Phase 1: Foundation & Extraction Flow (PR 1) ✅ COMPLETE

- [x] 1.1 Create `api/src/shared/flows/__init__.py` — package init exporting base types
- [x] 1.2 Create `api/src/shared/flows/base.py` — `GPUProfile` enum, `ImageArtifact` (with `volume_path` traversal guard and `media_type` validator for png/jpeg), `FlowOutput`, `BaseAtomicFlow` (Pydantic v2, `prompt` max 4000 chars)
- [x] 1.3 Create `api/src/shared/flows/extraction.py` — `ExtractionRequest(BaseAtomicFlow)` with `input_image: ImageArtifact` and optional `mask_margin`; `ExtractionFlow` binding `workflow_name="extraction"`, `gpu_profile=L4`, `timeout_s=300`
- [x] 1.4 Modify `api/src/shared/modal_config.py` — add BRIA RMBG custom node clone + pip install to `comfyui_run_commands`; add input_volume for artifact chaining
- [x] 1.5 Modify `api/src/shared/job_store.py` — add `artifacts: list | None` field to job state dict in `_store_job` / `_astore_job`
- [x] 1.6 Create `api/src/workflows/extraction/manifest.yaml` — inputs: `input_image` → LoadImage node, `prompt` unused; defaults: none; declare `outputs.artifacts: [{name: extracted_image, media_type: image/png, has_alpha: true}]`
- [x] 1.7 Create `api/src/workflows/extraction/workflow.json` — ComfyUI graph: LoadImage → BriaRMBG → SaveImage (RGBA PNG)
- [x] 1.8 Modify `api/src/shared/workflows/models.py` — extend `ManifestSchema` with optional `outputs` field containing `artifacts: list[dict]`
- [x] 1.9 Modify `api/src/features/generation/service.py` — add `dispatch_flow(job_id, flow_request)` method that loads engine via flow's `workflow_name`, resolves graph, validates models, spawns correct Modal GPU function; add `EXTRACTION_FLOW` to supported flows set
- [x] 1.10 Modify `api/src/features/generation/modal_tasks.py` — add `run_generation_l4` Modal function (L4, timeout=1800s) if not already present; ensure volume mount includes `/root/ComfyUI/input` for artifact chaining
- [x] 1.11 Modify `api/src/features/generation/router.py` — add `POST /generate/extraction` route accepting `ExtractionRequest`, returning 202 with `job_id`
- [x] 1.12 Create `api/src/tests/test_flow_base.py` — test `ImageArtifact` path traversal rejection, media_type validation, `BaseAtomicFlow` prompt length, `FlowOutput` contract
- [x] 1.13 Create `api/src/tests/test_extraction_flow.py` — test `ExtractionRequest` validation (missing input_image, invalid media_type), extraction workflow template loads, manifest declares output artifact

## Phase 2: Composition Flow (PR 2)

- [ ] 2.1 Create `api/src/shared/flows/composition.py` — `CompositionRequest(BaseAtomicFlow)` with `background_image`, `foreground_image: ImageArtifact`, `control_mode: Literal["depth","canny"]`, `control_strength: float` (0.0–2.0, default 1.0), optional `seed`; `CompositionFlow` binding `workflow_name="composition"`, `gpu_profile=L4`, `timeout_s=600`
- [ ] 2.2 Modify `api/src/shared/modal_config.py` — add `comfyui_controlnet_aux` custom node clone + pip install; add FLUX ControlNet depth/canny model filenames to whitelist
- [ ] 2.3 Create `api/src/workflows/composition/manifest.yaml` — inputs: `prompt`, `background_image` → LoadImage, `foreground_image` → LoadImage, `control_mode`, `unet`, `clip`, `vae`; defaults for model filenames
- [ ] 2.4 Create `api/src/workflows/composition/workflow.json` — ComfyUI graph: LoadImage(bg) → DepthPreprocessor/CLIPVisionEncode → ControlNetApply; LoadImage(fg) → VAEEncode → KSampler(FLUX UNet) → VAEDecode → SaveImage
- [ ] 2.5 Modify `api/src/features/generation/service.py` — register `COMPOSITION_FLOW` in supported flows; `dispatch_flow` handles composition routing
- [ ] 2.6 Modify `api/src/features/generation/router.py` — add `POST /generate/composition` route accepting `CompositionRequest`, returning 202
- [ ] 2.7 Create `api/src/tests/test_composition_flow.py` — test `CompositionRequest` validation (invalid control_mode, missing images, control_strength bounds), workflow template loads, manifest validation

## Phase 3: Identity Flow & Legacy Cleanup (PR 3)

- [ ] 3.1 Create `api/src/shared/flows/identity.py` — `IdentityRequest(BaseAtomicFlow)` with `reference_face: ImageArtifact`, optional `seed`, `width`/`height` (multiples of 64); `IdentityFlow` binding `workflow_name="identity"`, `gpu_profile=A100`, `timeout_s=1200`
- [ ] 3.2 Modify `api/src/shared/modal_config.py` — add `ComfyUI-PuLID-Flux` node already present; verify PuLID model in whitelist; add A100 GPU function reference
- [ ] 3.3 Create `api/src/workflows/identity/manifest.yaml` — inputs: `prompt`, `reference_face` → LoadImage, `seed`, `pulid`, `unet`, `clip`, `vae`, `face_detector`; defaults for model filenames
- [ ] 3.4 Create `api/src/workflows/identity/workflow.json` — ComfyUI graph: LoadImage(face) → PuLIDModelLoader → ApplyPuLID; CLIPTextEncode → KSampler(FLUX UNet) → VAEDecode → SaveImage
- [ ] 3.5 Modify `api/src/features/generation/modal_tasks.py` — add `run_generation_a100` Modal function (A100, timeout=3600s)
- [ ] 3.6 Modify `api/src/features/generation/service.py` — register `IDENTITY_FLOW`; remove `IDENTIDAD_GGUF_WORKFLOW` from `SUPPORTED_WORKFLOWS`; remove `identidad_gguf` branching from `enqueue_modal_work`; remove `resolve_identity_seed` and `download_image_to_base64` if unused
- [ ] 3.7 Modify `api/src/features/generation/router.py` — add `POST /generate/identity` route accepting `IdentityRequest`, returning 202
- [ ] 3.8 Modify `api/src/features/generation/models.py` — remove `identidad_gguf` from `WorkflowName` literal and `SUPPORTED_WORKFLOWS`; remove `image_url`, `width`, `height`, `seed` workflow-scoped validators for GGUF; add deprecation comment on `GenerateRequest`
- [ ] 3.9 Delete `api/src/workflows/identidad_gguf/` directory (workflow.json + manifest.yaml)
- [ ] 3.10 Update `api/src/tests/test_generation_models.py` — remove GGUF workflow tests; add tests for updated `WorkflowName`
- [ ] 3.11 Update `api/src/tests/test_generation_service.py` — remove GGUF branching tests; add `dispatch_flow` tests for all three new flows
- [ ] 3.12 Create `api/src/tests/test_identity_flow.py` — test `IdentityRequest` validation (non-multiple-of-64 dimensions, missing reference_face), workflow template loads
- [ ] 3.13 Update `api/src/tests/test_workflow_templates.py` — remove `identidad_gguf` template test; add extraction, composition, identity template validation tests
- [ ] 3.14 Update `api/src/tests/test_modal_config.py` — verify BRIA, ControlNet nodes in image build commands; verify updated whitelist
