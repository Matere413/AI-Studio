# Design: SDD-2 Modal Flows

## Technical Approach

Layer typed flow modules (`src/shared/flows/`) over the existing `WorkflowEngine`, keeping `workflow.json` + `manifest.yaml` as the single source of truth for ComfyUI graphs. Each flow module owns its Pydantic v2 request model, GPU profile, and image-input strategy — decoupling from the kitchen-sink `GenerateRequest`. `ImageArtifact` references pass between flows via Modal volume paths, eliminating Base64 roundtrips.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Flow models as Pydantic ABC vs per-flow standalone | ABC gives type contract; standalone is simpler | Standalone BaseAtomicFlow with per-flow children inheriting `workflow_name`, `gpu_profile`, `model_requirements` |
| Image input via LoadImage (native) vs custom LoadImageFromPath | Native LoadImage reads from `ComfyUI/input/`; custom node adds maintenance burden | Mount volume at `/root/ComfyUI/input/`, use native `LoadImage` — zero new custom nodes |
| GPU: separate Modal functions vs single function with dynamic profile | Dynamic switching avoids duplication; separate functions allow independent timeouts | Per-profile Modal functions: `run_generation_l4` (L4/1800s), `run_generation_a100` (A100/3600s) |

## Data Flow

```
POST /generate/{flow}     GenerationService        WorkflowEngine        Modal(fn)        ComfyUI
      │                       │                        │                    │               │
      ├─{FlowRequest}─────────►│                        │                    │               │
      │                       ├─load_engine(flow)──────►│                    │               │
      │                       │◄───engine───────────────┤                    │               │
      │                       ├─engine.execute(params)──►                    │               │
      │                       │◄───resolved_graph───────┤                    │               │
      │                       ├─spawn(gpu_profile)──────┼───────────────────►│               │
      │                       │                        │   [boot+run]       ├───prompt──────►│
      │                       │                        │                    │◄──output──────┤
      │                       │◄───image_path───────────┤                    │               │
      │◄──{job_id, status}────┤                        │                    │               │
```

**Image chaining path** (extraction → composition):
```
Extraction flow ──► image_volume:/output/{job_id}/extracted.png
                          │
                          ▼ ImageArtifact(volume_path=...)
Composition flow ◄────────┘ mounts to /root/ComfyUI/input/{job_id}.png ──► LoadImage node
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/shared/flows/__init__.py` | Create | Package init |
| `api/src/shared/flows/base.py` | Create | `BaseAtomicFlow`, `FlowOutput`, `ImageArtifact`, `GPUProfile` enum |
| `api/src/shared/flows/extraction.py` | Create | `ExtractionRequest`, `ExtractionFlow` — BRIA RMBG params |
| `api/src/shared/flows/composition.py` | Create | `CompositionRequest`, `CompositionFlow` — FLUX+ControlNet params |
| `api/src/shared/flows/identity.py` | Create | `IdentityRequest`, `IdentityFlow` — PuLID+FLUX params |
| `api/src/shared/modal_config.py` | Modify | Add L4/A100 GPU fns, BRIA/ControlNet nodes, `input_volume` mount |
| `api/src/features/generation/service.py` | Modify | Replace `enqueue_modal_work` branching with flow dispatch, remove `identidad_gguf` |
| `api/src/features/generation/models.py` | Modify | Deprecate `GenerateRequest` workflow scoping; keep legacy paths stable |
| `api/src/features/generation/router.py` | Modify | Add `/generate/extraction`, `/generate/composition`, `/generate/identity` routes |
| `api/src/workflows/extraction/` | Create | `workflow.json` + `manifest.yaml` for BRIA extraction |
| `api/src/workflows/composition/` | Create | `workflow.json` + `manifest.yaml` for FLUX+ControlNet |
| `api/src/workflows/identity/` | Create | `workflow.json` + `manifest.yaml` for PuLID+FLUX |
| `api/src/workflows/identidad_gguf/` | Delete | Replaced by identity flow |
| `api/src/shared/job_store.py` | Modify | Add `artifacts: list[ImageArtifact]` to job state |

## Interfaces / Contracts

```python
# api/src/shared/flows/base.py
from enum import Enum
from pydantic import BaseModel, Field

class GPUProfile(str, Enum):
    T4 = "T4"
    L4 = "L4"
    A100 = "A100"

class ImageArtifact(BaseModel):
    volume_path: str                    # /root/ComfyUI/output/job-{id}/file.png
    media_type: str = "image/png"
    source_job_id: str | None = None
    width: int | None = None
    height: int | None = None

class FlowOutput(BaseModel):
    job_id: str
    artifacts: list[ImageArtifact]

class BaseAtomicFlow(BaseModel):
    workflow_name: str
    gpu_profile: GPUProfile
    timeout_s: int
    prompt: str = Field(min_length=1, max_length=4000)
```

Per-flow request models extend `BaseAtomicFlow` with scoped fields (e.g., `ExtractionRequest` adds `input_image: ImageArtifact`, `CompositionRequest` adds `background_image: ImageArtifact` and `control_mode: Literal["depth","canny"]`, `IdentityRequest` adds `reference_face: ImageArtifact` and `seed: int`).

## ComfyUI Graph Structures

**BRIA Extraction** (L4/300s): LoadImage → BriaRMBG → SaveImage. Manifest declares `input_image` → LoadImage node, output is a transparent PNG. Requires custom node `ComfyUI-BRIA_AI-RMBG`.

**FLUX + ControlNet Composition** (L4/600s): LoadImage(bg) → DepthPreprocessor/CLIPVisionEncode → ControlNetApply. LoadImage(fg) → VAEEncode → KSampler(FLUX UNET, depth+fg conditioning) → VAEDecode → SaveImage. Manifest declares `prompt`, `background_image`, `foreground_image`, `control_mode`, `unet`, `clip`, `vae`. Requires `comfyui_controlnet_aux`.

**PuLID Identity** (A100/1200s): LoadImage(face) → PuLIDModelLoader → ApplyPuLID. CLIPTextEncode(prompt) → KSampler(FLUX UNET, PuLID conditioning) → VAEDecode → SaveImage. Manifest declares `prompt`, `reference_face`, `seed`, `pulid`, `unet`, `clip`, `vae`, `face_detector`. Requires `ComfyUI-PuLID-Flux`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `BaseAtomicFlow` validation, `ImageArtifact` path boundaries, flow model scoping | Pytest parametrized with valid/invalid inputs |
| Unit | `WorkflowEngine` integration with new manifests (node refs, whitelist checks) | Existing `test_workflow_engine.py` patterns extended |
| Integration | Flow → resolved graph → ComfyUI dry-run (no GPU) | Mock ComfyUIClient, verify graph structure |
| E2E | Full Modal spawn of extraction → composition chain | Requires Modal dev environment; manual gate |

## Migration / Rollout

Keep `flux2_txt2img` and `flux2_editing` unchanged. Add new flow endpoints under `/generate/{flow}` alongside legacy `/generate`. Once identity flow is validated, remove `identidad_gguf` workflow directory and its routing from `service.py`. No data migration required — new flows use the same `model_volume` and `image_volume`.

## Open Questions

- [ ] `ComfyUI-BRIA_AI-RMBG` custom node compatibility with FLUX environment — verify no dependency conflicts with existing PuLID/GGUF nodes.
- [ ] A100 GPU availability/cost in current Modal region — confirm before implementing identity flow.
- [ ] ControlNet model weights (depth/canny for FLUX) — verify availability on HuggingFace and whitelist filenames.
