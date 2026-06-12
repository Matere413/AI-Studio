# Design: ComfyUI Studio Workflows

## Technical Approach

Implement a **Hybrid Template + Node Map** architecture to decouple the Python API from brittle ComfyUI node IDs. A new `WorkflowEngine` will load static ComfyUI JSON templates alongside YAML manifests, applying runtime inputs (e.g., prompts, checkpoints) dynamically to the graph. A `ModelDownloader` Modal function will manage on-demand `.safetensors` caching into a persistent Modal Volume. Endpoints (`/generate`, `/edit`) will use Pydantic models to validate dynamic inputs and execute the resolved graphs.

## Architecture Decisions

### Decision: Manifest Format

**Choice**: YAML for manifests (`manifest.yaml`) mapped to JSON templates (`workflow.json`).
**Alternatives considered**: JSON for both; hardcoding node IDs in Python.
**Rationale**: YAML provides better human readability and comment support for mapping semantic inputs (e.g., `prompt: { node_id: "3", field: "text" }`), while the template remains unmodified from ComfyUI exports.

### Decision: Model Caching Strategy

**Choice**: Dedicated Modal function `download_model` utilizing `httpx` to stream weights to a mounted Modal Volume.
**Alternatives considered**: Downloading locally before deploying; downloading within the ComfyUI container directly.
**Rationale**: A separate Modal function can be invoked synchronously/asynchronously to ensure the weight is ready on the volume before the workflow executes, centralizing cache logic and avoiding timeouts.

### Decision: Parameter Validation

**Choice**: Pydantic v2 dynamic schemas extending base models.
**Alternatives considered**: Loose `Dict[str, Any]` validation.
**Rationale**: Pydantic maintains strict API documentation and type safety, ensuring incoming API requests match the requirements of the workflow manifests.

## Data Flow

    Client (FastAPI) 
         │ 1. POST /generate (Prompt, Checkpoint URL)
         ▼
    Endpoint Layer (Pydantic Validation)
         │ 2. Trigger Model Cache
         ├──────── ModelDownloader (Modal) ──→ Modal Volume (/models)
         │ 
         ▼ 3. Init Engine
    WorkflowEngine 
         │ 4. Load & Resolve
         ├──────── src/workflows/ (JSON Template + YAML Manifest)
         │
         ▼ 5. Execute Graph
    ComfyUI WebSocket Client ──→ ComfyUI Instance

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/shared/workflows/engine.py` | Create | Contains the `WorkflowEngine` class logic. |
| `src/shared/workflows/models.py` | Create | Pydantic v2 models (`ManifestSchema`, `NodeMapping`). |
| `src/shared/workflows/cache.py` | Create | Modal `download_model` function definition. |
| `src/workflows/txt2img/` | Create | Directory for text-to-image template and manifest. |
| `src/features/generation/schemas.py` | Modify | Update base schemas to support checkpoint/LoRA parameters. |
| `src/features/generation/router.py` | Modify | Use `WorkflowEngine` and `download_model` in `/generate`. |
| `src/features/editing/` | Create | New feature directory for the `/edit` (img2img) endpoint. |
| `src/features/controlnet/` | Create | New feature directory for ControlNet workflows. |

## Interfaces / Contracts

### Workflow Engine Classes

```python
from pydantic import BaseModel
from typing import Any, Dict

class NodeMapping(BaseModel):
    node_id: str
    field: str

class ManifestSchema(BaseModel):
    inputs: Dict[str, NodeMapping]

class WorkflowEngine:
    def __init__(self, template_path: str, manifest_path: str):
        # Loads JSON template and YAML manifest
        pass

    def apply_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Maps runtime params to the JSON graph using manifest mappings
        pass

    async def execute(self, params: Dict[str, Any]) -> str:
        # Applies parameters and dispatches to ComfyUI client
        pass
```

### Modal ModelDownloader

```python
import modal

volume = modal.Volume.from_name("comfy-models-disk")
app = modal.App("model-cache")

@app.function(volumes={"/models": volume}, timeout=600)
def download_model(url: str, filename: str) -> str:
    # Streams file from URL to /models/filename if not exists
    # Returns the absolute path on the volume
    pass
```

### API Schemas

```python
from pydantic import BaseModel, Field

class GenerationRequest(BaseModel):
    prompt: str = Field(..., description="The main text prompt.")
    checkpoint_url: str | None = Field(None, description="Optional custom .safetensors URL.")
    lora_url: str | None = Field(None, description="Optional custom LoRA URL.")
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `WorkflowEngine` | Mock file system; assert `apply_parameters` mutates graph correctly. |
| Unit | Manifest Models | Pydantic validation of missing fields/invalid node references. |
| Integration | `download_model` | Test modal function with a small mock file; verify cache hits. |
| E2E | `/generate` API | Test full flow with default template, mocking ComfyUI WS client. |

## Migration / Rollout

No database migration is required. The `/generate` endpoint will seamlessly shift to the template-based approach while keeping backwards compatibility for requests containing only a `prompt`. Modal volume `comfy-models-disk` must be created if it does not exist.

## Open Questions

- [ ] Is there a cap on the maximum `.safetensors` size we should allow the `download_model` function to process?
- [ ] Should `download_model` use a checksum validation before marking the file as fully cached?
