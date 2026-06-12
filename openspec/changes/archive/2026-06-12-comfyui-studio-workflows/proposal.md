# Proposal: ComfyUI Studio Workflows

## Intent

Upgrade the MVP generation API into a ComfyUI Studio supporting complex workflows (Checkpoints, LoRAs, ControlNet, img2img). The current system hardcodes a single txt2img workflow and brittle node IDs. We need dynamic workflow parameterization, model weight caching, and a scalable directory structure.

## Scope

### In Scope
- Hybrid Template + Node Map architecture for decoupling ComfyUI JSON from Python code
- Download and cache `.safetensors` weights into the existing Modal volume
- Extract `src/shared/workflow_engine.py` to power multiple features
- Standardize `/generate` endpoint and add `/edit` (img2img) and ControlNet endpoints

### Out of Scope
- Custom model training or fine-tuning
- Video generation workflows
- Multi-GPU parallel execution

## Capabilities

### New Capabilities
- `workflow-engine`: Generic ComfyUI workflow execution via template + manifest mapping
- `model-weight-caching`: Download and cache `.safetensors` into Modal Volume at runtime
- `image-editing`: img2img endpoint with image upload and parameterization
- `controlnet`: ControlNet workflows with preprocessor support

### Modified Capabilities
- `image-generation`: Extend from hardcoded txt2img to dynamic checkpoint/LoRA selection

## Approach

Adopt a **Hybrid Template + Node Map** architecture: static ComfyUI JSON templates stored in `src/workflows/` with a YAML manifest mapping semantic parameters (prompt, checkpoint, lora, image) to node IDs. This decouples code from brittle node IDs. A new `WorkflowEngine` class in `src/shared/workflow_engine.py` will load templates, apply manifests, and execute via the existing WebSocket client. Model weights will be downloaded on-demand into the Modal Volume using a dedicated `ModelCache` service.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/shared/workflow_engine.py` | New | Generic workflow execution engine |
| `src/shared/model_cache.py` | New | On-demand model weight downloader |
| `src/features/generation/` | Modified | Standardize `/generate` with dynamic workflows |
| `src/features/editing/` | New | img2img endpoint |
| `src/features/controlnet/` | New | ControlNet endpoint |
| `src/workflows/` | New | JSON templates and YAML manifests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Model weight download failures | Med | Retry with exponential backoff; validate checksums |
| Brittle node IDs in exported JSON | Med | Enforce manifest validation on template load |

## Rollback Plan

Revert the router imports to the current hardcoded `comfy_client.py` and `payload.json`. Keep the old `GenerationService` implementation behind a feature flag or branch.

## Dependencies

- Modal Volume `comfy-models-disk` for weight storage
- ComfyUI `/upload/image` endpoint for img2img/ControlNet inputs

## Success Criteria

- [ ] `/generate` supports checkpoint and LoRA selection via parameters
- [ ] `/edit` accepts an image and returns an edited result
- [ ] ControlNet endpoint accepts control image and type
- [ ] Model weights download and cache correctly on first use
- [ ] All existing `image-generation` tests pass without modification

## Proposal Question Round

Before finalizing, review these assumptions:
1. Should the first slice include LoRA support, or defer to a later phase?
2. Is img2img (`/edit`) the highest priority after standardizing `/generate`, or is ControlNet more urgent?
3. Do we need a model registry (database of allowed URLs/checksums) or is a simple allow-list sufficient for the first slice?
4. Should the manifest format be YAML, or would JSON be preferred for consistency with ComfyUI exports?
5. Are we targeting a single checkpoint per workflow, or multi-checkpoint pipelines from the start?

Please confirm or correct these assumptions before we proceed to specs.
