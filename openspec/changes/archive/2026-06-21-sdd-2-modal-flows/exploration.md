# Exploration: sdd-2-modal-flows

## Goal

Stand up the SDD 2 "Librería de Flujos Base y Estandarización Modal (Calidad Core)" by
turning the three target atomic flows — **Extraction/Isolation** (Rembg/BRIA),
**Composition** (FLUX + ControlNet Depth/Canny), and **Identity** (IP-Adapter/FaceID) — into
predictable, composable "Lego blocks" the orchestrator can chain.

This document audits the current API↔Modal↔ComfyUI plumbing, identifies the gaps that
prevent treating flows as Lego blocks today, and compares the candidate standardization
approaches.

## Current State

The project already has a working pipeline that loads ComfyUI API-format JSON, mutates
it from a typed FastAPI request, ships it to Modal, boots ComfyUI headless inside the
container, executes the graph, and streams lifecycle events back over WebSocket. The
shape is correct, but it was built for *one router and one feature* (`generation`). SDD
2 needs to scale that shape to multiple atomic flows without copy-pasting routing,
validation, Modal spawn, and image-handle plumbing each time.

### Pipeline shape (existing)

```
Client (Next.js)                        Modal
   │                                      │
   │ POST /generate  (request/prompt)     │
   │ ───────────────────────────────────► │ FastAPI (api/app.py)
   │                                      │  └─ generation_router
   │                                      │     └─ GenerationService
   │                                      │        └─ WorkflowEngine
   │                                      │           ├─ workflow.json (template)
   │                                      │           └─ manifest.yaml  (semantic map)
   │                                      │        └─ run_generation.spawn (T4) ─┐
   │ ◄── 202 + job_id                     │                                   │
   │                                      │  Modal function:                    │
   │ WS /ws/generate/{job_id} ──────────► │   _boot_comfyui (subprocess)        │
   │                                      │   ComfyUIClient.queue_prompt(graph) │
   │ ◄── progress / completed             │   stream_progress()                 │
   │                                      │   resolve_output_path() ────────────┘
   │ GET /images/{job_id}                 │
   │ ───────────────────────────────────► │ image_volume.reload() + FileResponse
```

### Atomic flows present today

| Folder (`api/src/workflows/<name>/`) | Role | GPU | Inputs | Outputs |
|---|---|---|---|---|
| `flux2_txt2img` | Text → image (FLUX 2 + Turbo LoRA) | T4 | `prompt`, `use_turbo` | image |
| `flux2_editing` | Image edit (FLUX 2 + ReferenceLatent) | T4 | `prompt`, `image_base64`, `use_turbo` | image |
| `identidad_gguf` | Identity preservation (FLUX GGUF + PuLID + FaceDetailer) | L4 (`run_generation_heavy`) | `prompt`, `image_url`, `width`, `height`, `seed` | image |

The router and service are wired only for these three names. `src/features/editing/` and
`src/features/controlnet/` are empty stub folders.

### Key files and what they do

- `api/app.py` — Modal ASGI entry. Wires CORS, includes `generation_router`, defines the
  `comfy_image` and the two volumes (`comfy-models-disk`, `comfy-output-disk`).
- `api/src/shared/modal_config.py` — `comfy_image` (ComfyUI + GGUF + PuLID + Impact
  Pack + custom `LoadImageFromBase64` node), `default_whitelist` for all model
  categories, and the two volumes.
- `api/src/shared/workflows/engine.py` — `WorkflowEngine` (loads `workflow.json` +
  `manifest.yaml`, validates node references, applies typed params to a deep copy of
  the graph). The reusable spine of the system.
- `api/src/shared/workflows/cache.py` — `load_whitelist()` reads `ALLOWED_MODELS_JSON`
  env; `resolve_cached_model()` enforces the "pre-cached only" V1 boundary (raises
  `ModelNotCachedError` on miss).
- `api/src/shared/workflows/models.py` — Pydantic `ManifestSchema` (`inputs: dict[NodeMapping]`,
  `defaults`, `formats`, `prompt_templates`, `persona_metadata`).
- `api/src/shared/comfy_client.py` — Low-level WS + HTTP wrapper. Includes
  `LoadImageFromBase64` custom node (synchronous base64 path through ComfyUI).
- `api/src/shared/job_store.py` — `JobStore` wrapping `modal.Dict.from_name("api-blanca-jobs")`.
  Stores `{status, image_path, error_code, error_detail, progress, message}`.
- `api/src/features/generation/router.py` — `POST /generate`, `GET /images/{job_id}`,
  `WS /ws/generate/{job_id}`. Hard-codes the three workflow names.
- `api/src/features/generation/service.py` — `GenerationService.enqueue_modal_work` is
  the single point where the router dispatches to one of the three flows. **This is
  where the if/else forest lives** (lines 190-227): it branches on
  `FLUX2_TXT2IMG_WORKFLOW`, `FLUX2_EDITING_WORKFLOW`, `IDENTIDAD_GGUF_WORKFLOW` to
  decide which params to assemble, which Modal function to call, and whether to
  download an `image_url` to base64 inline.
- `api/src/features/generation/modal_tasks.py` — Two Modal functions:
  `run_generation` (T4, 1200s) and `run_generation_heavy` (L4, 1800s). Both call
  `_execute_generation`, which boots ComfyUI as a subprocess, queues the prompt, and
  streams progress. **Duplicated** between the two functions (only the GPU and timeout
  differ).
- `api/src/features/generation/models.py` — `GenerateRequest` (Pydantic v2,
  `extra="forbid"`) is the single entrypoint. Workflow-scoped fields are validated with
  `model_validator(mode="after")`: `use_turbo` only for Flux flows, `image_base64` only
  for `flux2_editing`, `image_url` only for `identidad_gguf`, etc.
- `api/sync_models.py` — Modal housekeeping script for the model Volume (delete retired
  weights, pull FLUX 2 assets).
- `api/src/tests/test_workflow_templates.py`, `test_flux2_workflow_assets.py` — Contract
  tests already enforce that every supported workflow has both `workflow.json` and
  `manifest.yaml` and that the manifest's `node_id` references resolve into the
  template.

### Image-handle status quo

| Producer → Consumer | Mechanism | Coupling |
|---|---|---|
| HTTP client → `flux2_editing` | `image_base64` in body, written into `LoadImageFromBase64` (custom node) | Tight — service injects base64 directly into the graph; payload bloats |
| HTTP client → `identidad_gguf` | `image_url` in body, service fetches with `httpx` and injects base64 | **Service is the fetcher**, not the engine — leaks HTTP into business layer |
| Upstream flow → downstream flow | None today (each flow is terminal) | The orchestrator cannot chain flows because there is no shared image handle type |

### Test discipline already in place

- `pytest` installed, `strict_tdd: true` in `openspec/config.yaml`.
- Contract tests for each workflow template and engine behavior exist.
- Test pattern is small unit + golden-file (manifest schema + workflow JSON shape).

## Affected Areas

| Path | Why it is affected |
|---|---|
| `api/src/features/generation/router.py` | Currently a hard-coded triple switch; needs to be replaced by a registry of atomic flows. |
| `api/src/features/generation/service.py` | `enqueue_modal_work` is a 50-line conditional on workflow name; needs to become a generic dispatcher. |
| `api/src/features/generation/modal_tasks.py` | Two Modal functions duplicated except for GPU/timeout. SDD 2 likely needs more (Rembg is CPU, ControlNet wants more VRAM, FaceID wants more VRAM). |
| `api/src/features/generation/models.py` | `GenerateRequest` enumerates every field per workflow with `Literal` workflow names and `model_validator` cross-checks. Adding three flows breaks the Literal and the validator. |
| `api/src/shared/modal_config.py` | `comfyui_run_commands` clones GGUF + PuLID + Impact-Pack today. SDD 2 needs ControlNet nodes (`comfyui_controlnet_aux` or `ComfyUI-Advanced-ControlNet`), IP-Adapter nodes (`ComfyUI_IPAdapter_plus`), and possibly `rembg` Python package. |
| `api/src/shared/workflows/engine.py` | The engine is reusable, but its `apply_parameters` is unaware of image-handle types. Image inputs are passed as opaque strings, and the engine has no concept of "input image" vs "output image." |
| `api/src/shared/workflows/models.py` | `ManifestSchema` has `inputs` and `defaults` but no `outputs` and no `artifacts` (typed I/O contract). |
| `api/src/shared/comfy_client.py` | `LoadImageFromBase64` is the only image-input path. SDD 2 likely needs an image-input node that takes a `modal.Dict` or volume path (e.g. `LoadImageFromVolume`) so the orchestrator can hand upstream outputs to downstream flows without round-tripping through base64. |
| `api/src/features/editing/`, `api/src/features/controlnet/` | Empty stubs. SDD 2 will move from "one feature module" to "one atomic flow per feature module." |
| `api/src/workflows/` | Currently has three folders. SDD 2 will add three more (`extraction_isolation`, `composition`, `identity_ipadapter`) — each must follow the existing template + manifest pattern. |
| `api/src/shared/job_store.py` | `JobStore` records the *terminal* state. Atomic flows are intermediate, so the store needs an `output_artifacts` field so the orchestrator can hand outputs to the next flow. |
| `openspec/specs/` | New spec folders needed: `extraction-isolation-workflows`, `composition-workflows`, `identity-workflows`. The `workflow-engine` spec needs a delta to formalize atomic-flow contract. |
| `view/` (Next.js) | Out of scope for SDD 2 (this is "Calidad Core" — backend only). The frontend change that exposes these flows lives in a separate SDD. |

## Approaches

Three plausible strategies for turning flows into Lego blocks. All assume the
`workflow.json` + `manifest.yaml` pattern stays (it is solid, well-tested, and already
familiar). The variable is **what abstraction wraps a single flow**.

### Option A — Per-flow feature modules + a generic dispatcher

Promote each atomic flow to a self-contained Python module:

```
api/src/features/
  generation/                 # legacy router kept for back-compat
  extraction_isolation/
    router.py                 # POST /extraction/isolate
    service.py
    modal_tasks.py
  composition/
    router.py                 # POST /composition/render
    service.py
    modal_tasks.py
  identity/
    router.py                 # POST /identity/preserve
    service.py
    modal_tasks.py
```

Plus a `BaseAtomicFlow` (or `FlowSpec`) in `src/shared/flows/` that each flow extends:

```python
class AtomicFlow(Protocol):
    name: str
    request_model: Type[BaseModel]
    response_model: Type[BaseModel]
    manifest_path: str
    template_path: str
    gpu: str
    timeout_s: float
    async def execute(self, request) -> FlowOutput: ...
```

The orchestrator (in a future SDD, but the seam is added here) becomes a stateless
function that calls `flow.execute(request)` and chains outputs to inputs.

- **Pros**: Strict hexagonal split, each flow is testable in isolation, no central
  if/else forest, easy to add a fourth/fifth flow. Reuses the existing
  `WorkflowEngine` (it is already framework-agnostic). Test surface is "one feature
  module → one test directory." Aligns with the project rule that each feature is its
  own module (`AGENT.md`).
- **Cons**: Three new feature folders duplicate boilerplate (router, service,
  modal_tasks, tests). Mitigation: a `BaseAtomicFlow` in `shared/flows/` factors the
  Modal spawn + job-store write + WebSocket event logic.
- **Effort**: **Medium** for the framework + the three flows (estimated 800-1200 LOC
  including tests; will exceed 400-line PR budget → chained PRs needed).

### Option B — Registry inside the existing `generation` feature

Keep one router/service, but parameterize on a `FlowRegistry` keyed by atomic-flow
name. The router accepts a `flow` discriminator and the service dispatches via a
registry.

```
api/src/features/generation/
  router.py          # POST /flows/{flow_name}/run
  service.py
  flow_registry.py   # maps flow_name → FlowSpec
api/src/flows/       # the actual flow specs (one file per atomic flow)
  extraction_isolation.py
  composition.py
  identity.py
```

- **Pros**: Single router, single service, smaller blast radius. The `FlowRegistry`
  pattern is a natural extension of the existing `SUPPORTED_WORKFLOWS` set in
  `service.py` lines 17-21.
- **Cons**: Violates the "one feature = one module" rule from `AGENT.md`. Future flows
  (Style Transfer, Upscale, Voice Lip-Sync) pile up in `generation/`. The
  `generation` feature becomes a kitchen sink. `GenerateRequest` is already a kitchen
  sink of workflow-scoped fields and gets worse.
- **Effort**: **Low** (~400-600 LOC). Fits a single PR.

### Option C — Modal-native flows with a thin Python shell

Move the orchestration layer into Modal itself: define each flow as a Modal `cls` or a
dedicated Modal function, and keep the FastAPI layer as a thin "submit job" facade
that hands off to Modal via `.spawn()`. The Python service is mostly a router and a
manifest loader.

- **Pros**: Native to Modal, leverages Modal's autoscaling, Modal.Dict for inter-step
  state. Modal handles retries and dead-letter naturally.
- **Cons**: Modal is not designed for long, *chained* graph orchestration. State that
  has to outlive a single function call still needs a DTO. Loses the "service layer
  with hexagonal architecture" story the team has been building. Heavy coupling to
  Modal's primitives, which is exactly what the project's
  "ComfyUI doesn't know about business model" rule wants to avoid.
- **Effort**: **Medium-High** (~700-1000 LOC), but with a higher conceptual cost
  (rewrite the architectural mental model).

## Recommendation

**Adopt Option A** with two pragmatic concessions:

1. **Keep the `workflow.json` + `manifest.yaml` pattern** for every new flow. It is
   the smallest contract that already passes contract tests in
   `test_workflow_templates.py`.
2. **Add a `BaseAtomicFlow` protocol in `api/src/shared/flows/base.py`** so each new
   feature module is mostly declarative (manifest path, GPU, timeout, input/output
   models) and the heavy lifting (boot ComfyUI, queue prompt, stream progress, commit
   volume, write job) is shared.
3. **Standardize the image handle**: introduce an `ImageArtifact` Pydantic model in
   `api/src/shared/artifacts.py` with a discriminator (`url | volume_path | base64`)
   and a `LoadImageFromArtifact` custom node. This is the only way the Composition
   flow can consume the Extraction flow's output without round-tripping through HTTP.
4. **Defer the orchestrator to a follow-up SDD** ("Lego Orchestrator"). SDD 2's job is
   to put the Lego blocks on the table; the orchestrator is the kid who clicks them
   together. But the seam must be designed now (`AtomicFlow.execute()` returns an
   `ArtifactBag`).

### Why not Option B (registry inside `generation/`)?

Because the next three flows are not variations of "generation" — they are
*composable primitives* (extraction is a pre-processor, composition is a generator,
identity is a condition). Stuffing them under `generation/` invites the same if/else
forest that `enqueue_modal_work` already has, just one level higher.

### Why not Option C (Modal-native)?

The architecture rule in `AGENT.md` says: *"La capa de inferencia (ComfyUI) NO conoce
el modelo de negocio, solo ejecuta grafos matemáticos."* Option C inverts this — the
business model gets baked into Modal functions. We lose the testability and the
"operate on JSON dicts" clarity that has served the project well.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chained PRs grow past 400-line review budget | **High** | Medium | Plan PR slicing before apply: (1) `BaseAtomicFlow` + Artifact model, (2) Extraction flow, (3) Composition flow, (4) Identity flow. The first slice is a refactor, the next three are additive. |
| Adding 3 more custom-node families bloats the Modal image build time | Med | High | Pin nodes in `comfyui_run_commands` and parallelize `pip install`; cache the `Image` aggressively. Validate cold-boot time on a T4 before merging. |
| `LoadImageFromBase64` is the only image-input path — it round-trips through HTTP | High | Med | Add a `LoadImageFromArtifact` custom node that takes a path inside `image_volume` (zero-copy handoff between flows). |
| Manifest schema does not declare outputs | Med | Med | Add `outputs: dict[str, OutputMapping]` to `ManifestSchema` so a downstream flow can validate which nodes are outputs at registration time. |
| Existing `GenerateRequest` enumerates workflow names as `Literal` | High | Low | Keep `GenerateRequest` for back-compat but stop extending it; new flows get their own Pydantic models. `GenerateRequest` becomes a deprecated alias for `Flux2Request` union. |
| Pydantic v2 cross-field validation explodes with more workflow-scoped fields | Med | Med | Move workflow-scoped validation to the flow module, not the request model. The request model becomes thin. |
| Empty stubs `features/editing/` and `features/controlnet/` confuse the next agent | Low | Low | Delete the empty stubs in the refactor slice; document that flows are no longer namespaced by feature. |
| VRAM estimate for IP-Adapter (FLUX) + ControlNet on T4 is tight | Med | High | `ipadapter-faceid-plusv2_sdxl.bin` is already in `MODELS_TO_DELETE` (it was an old SDXL variant). Replace with `ip-adapter-faceid-portrait-v11.bin` or FLUX-native IP-Adapter (e.g. `flux-ip-adapter-v2.safetensors` if available). Validate before merging. |
| ComfyUI controlnet nodes are unstable across releases | Med | Med | Pin a known-good commit hash in `comfyui_run_commands` (today's `git clone` is unpinned). |

## Recommended First Slice (for the next phase)

`BaseAtomicFlow` + `ImageArtifact` + the deletion of empty `features/editing/` and
`features/controlnet/` stubs. This is the seam; the three flow implementations are
follow-up slices.

Concretely:

1. `api/src/shared/flows/__init__.py`
2. `api/src/shared/flows/base.py` — `AtomicFlow` Protocol + `BaseAtomicFlow`
   abstract class with a `_run_impl` template method.
3. `api/src/shared/artifacts.py` — `ImageArtifact` discriminated union.
4. `api/src/shared/modal_config.py` — append the new custom node clones in a
   separate `comfyui_run_commands_extra` list (keeps existing image build reproducible
   until the next slice merges).
5. `api/src/shared/workflows/models.py` — add `outputs: dict[str, OutputMapping]` to
   `ManifestSchema` (optional, defaults to empty).
6. Tests: `test_atomic_flow.py`, `test_image_artifact.py`.
7. `openspec/specs/workflow-engine/` — delta spec for the atomic-flow contract.

## Open Questions for the User

1. **GPU profile per flow** — confirm: Extraction = CPU-only (Rembg/BRIA are
   small), Composition = L4 (ControlNet wants more VRAM), Identity = L4 (IP-Adapter
   adds ~4GB). Or do we want a single GPU for all flows (T4) and just accept slower
   Composition/Identity?
2. **IP-Adapter model** — FLUX-native IP-Adapter vs SDXL IP-Adapter + FLUX base. The
   whitelist currently has `pulid_flux_v0.9.1.safetensors` (PuLID) but the SDD calls
   for IP-Adapter/FaceID. Are these two separate identity methods, or should
   `identidad_gguf` be replaced by an IP-Adapter flow?
3. **Extraction library** — Rembg (Python, CPU, easy) vs BRIA (ComfyUI node, more
   control, GPU). Pick one or both?
4. **Composition reference image** — does the Composition flow accept (prompt +
   control image + control type) or (prompt + control type) where the orchestrator
   generates the control image from a prior flow output?
5. **Should the orchestrator SDD be merged immediately after SDD 2**, or kept
   separate so SDD 2 can ship and stabilize first?

## Ready for Proposal

**Yes, with conditions.** The architectural gaps are clear, the candidates are
honestly compared, and the recommendation is grounded in the project's existing
rules (`AGENT.md`) and tested patterns (`WorkflowEngine`, contract tests). The
proposal phase should answer the open questions above before locking the approach,
and the first implementation slice must be the `BaseAtomicFlow` + `ImageArtifact`
seam (Option A) so the three flow implementations are additive, not interleaved.
