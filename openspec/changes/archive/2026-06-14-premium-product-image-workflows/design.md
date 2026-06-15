# Design: Premium Product Image Workflows

## Technical Approach

Add a prompt-first `product_premium` workflow on top of the existing FastAPI → `GenerationService` → `WorkflowEngine` → Modal ComfyUI path. The first slice accepts `workflow = "product_premium"` (aliasing to existing `workflow_name` internally for compatibility), an optional `format`, and no reference image. Studio vs lifestyle remains prompt intent, not a separate UI preset or API enum.

The workflow directory provides the ComfyUI API graph plus manifest-owned defaults for checkpoint and T4-safe square/vertical dimensions. Existing whitelist/cache validation remains the gate before Modal spawn.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Product intent model | Single `product_premium` workflow with free-form prompt and optional `format` | Separate `studio`/`lifestyle` workflows or style presets | Matches prompt-first specs and avoids closed menus while allowing both intents through wording. |
| Format resolution | Store `square`/`vertical` dimensions in `api/src/workflows/product_premium/manifest.yaml`; service expands `format` into `width`/`height` before graph execution | Hardcode dimensions in `GenerationService` or `WorkflowEngine` | Keeps T4-safe values workflow-owned and testable without changing engine for every future format. |
| Model gate | Declare the default premium checkpoint in the workflow graph/manifest and validate via current whitelist + `resolve_cached_model()` before spawn | Runtime downloads or user-selected models | Preserves the completed real ComfyUI integration boundary: no runtime model downloads, fail fast on missing cache. |
| Reference images | Explicitly omit `image_url`/upload/reference fields for `product_premium` now | Add hidden reference support | User decision: first slice is prompt-only. The contract leaves room for future image-guided fidelity through new fields later. |

## Data Flow

```text
Sidebar prompt + workflow/format
  -> submitGenerate({ prompt, workflow: product_premium, format })
  -> POST /generate GenerateRequest
  -> GenerationService.enqueue_modal_work(format)
  -> WorkflowEngine(product_premium manifest + workflow.json)
  -> whitelist/cache validation
  -> run_generation.spawn(job_id, resolved_graph)
  -> ComfyUI on Modal T4 -> WebSocket job events -> image serving
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/src/workflows/product_premium/workflow.json` | Create | ComfyUI API graph tuned for premium product image generation. |
| `api/src/workflows/product_premium/manifest.yaml` | Create | Maps `prompt`, `checkpoint`, `width`, `height`; declares `format` enum/default and square/vertical dimensions. |
| `api/src/shared/workflows/models.py` | Modify | Extend manifest schema with optional product format metadata and default checkpoint declaration. |
| `api/src/shared/workflows/engine.py` | Modify | Validate manifest metadata, expose format/default metadata, and reject non-whitelisted manifest checkpoint at load. |
| `api/src/features/generation/models.py` | Modify | Add `workflow`, keep `workflow_name`, and add `format: Literal["square", "vertical"] = "square"` with product-only validation. |
| `api/src/features/generation/router.py` | Modify | Pass normalized workflow and optional format to service. |
| `api/src/features/generation/service.py` | Modify | Normalize workflow name, expand product `format` to manifest dimensions, and keep cache validation before Modal spawn. |
| `api/src/shared/modal_config.py` | Modify | Add the approved premium checkpoint filename to `default_whitelist`. |
| `view/src/stores/generationStore.ts` | Modify | Add `product_premium` workflow and optional `format` type/validation. |
| `view/src/lib/api.ts` | Modify | Submit the product workflow payload unchanged. |
| `view/src/components/studio/Sidebar.tsx` | Modify | Add Product workflow chip and show only prompt plus square/vertical toggle for product mode; hide checkpoint/LoRA inputs. |
| `api/src/tests/*`, `view/src/**/*.test.*` | Modify/Create | Cover request validation, manifest loading, format resolution, cache errors, and product UI controls. |

## Interfaces / Contracts

```python
class GenerateRequest(BaseModel):
    prompt: str
    workflow: Literal["txt2img", "img2img", "controlnet", "product_premium"] | None = None
    workflow_name: Literal["txt2img", "img2img", "controlnet", "product_premium"] = "txt2img"
    format: Literal["square", "vertical"] = "square"
```

Contract rule: `format` is accepted only when normalized workflow is `product_premium`; invalid values fail Pydantic validation. No `reference_image`, `image_url`, or upload contract is added for this slice.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Manifest schema, whitelist rejection, format-to-dimensions expansion | Extend `test_workflow_models.py`, `test_workflow_engine.py`, `test_generation_service.py`. |
| Integration | `POST /generate` accepts product square/vertical, rejects invalid format, maps cache errors | Extend `test_generation_router.py` with mocked spawn/cache. |
| Frontend | Product chip, prompt-first controls, format toggle payload, no style/model controls | Extend `generationStore.test.ts` and `Sidebar.test.tsx`. |

## Migration / Rollout

No data migration required. Roll out by adding the workflow and whitelist entry; rollback removes `product_premium` files, request fields remain backward compatible.

## Open Questions

- [ ] Which exact premium checkpoint filename is approved and already present in the Modal Volume?
