# Tasks: Persona Identity Preservation

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600–800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Infra + Graph) → PR 2 (API) → PR 3 (Frontend) |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Modal infra + workflow graph | PR 1 | Base = `feature/persona-identity-preservation` tracker branch. Whitelist models, install node, update workflow.json + manifest.yaml |
| 2 | Backend API layer | PR 2 | Base = PR 1 branch. Models, service, router changes + backend tests |
| 3 | Frontend UI | PR 3 | Base = PR 2 branch. Store, types, client, upload component + frontend tests |

## Phase 1: Modal Infrastructure + Workflow Graph

- [x] 1.1 `modal_config.py`: add RealVisXL_V4.0, FaceID adapter, CLIP Vision to whitelist; add `ComfyUI_IPAdapter_plus` to `run_commands`
- [x] 1.2 `manifest.yaml`: set `default_checkpoint` to `RealVisXL_V4.0.safetensors`; add `image_url` and `faceid_strength` inputs; remove `v1_excluded_nodes` IPAdapter entry
- [x] 1.3 `workflow.json`: add LoadImageFromBase64, IPAdapterModelLoader, CLIPVisionLoader, IPAdapterFaceIDPlusV2 nodes; rewire KSampler `model` input to IP-Adapter output
- [x] 1.4 Verify: workflow resolves with `faceid_strength=0` and `faceid_strength=0.75` without errors

## Phase 2: Backend API Layer

- [x] 2.1 `models.py`: add `image_url: Optional[str]` field with URL/data URI validation on `GenerateRequest`
- [x] 2.2 `service.py`: pass `image_url` to params; set `faceid_strength=0.75` when present, `0` when absent
- [x] 2.3 `router.py`: forward `request.image_url` to `enqueue_modal_work`
- [x] 2.4 Test: parametrize `GenerateRequest` validation for URL, data URI, invalid format, None
- [x] 2.5 Test: `enqueue_modal_work` passes correct params with/without `image_url` (mocked engine)
- [x] 2.6 Test: `POST /generate` accepts `image_url` and returns 202

## Phase 3: Frontend UI

- [x] 3.1 `types.ts`: add `image_url?: string` to `GenerationParameters`
- [x] 3.2 `generationStore.ts`: add `referenceFaceUrl`, `setReferenceFaceUrl`, `clearReferenceFace`; include `image_url` in normalized params
- [x] 3.3 `client.ts`: include `image_url` in submit payload when present
- [x] 3.4 `useGenerationFlow.ts`: read `referenceFaceUrl` from store, pass as `image_url` in generation params
- [x] 3.5 `PromptPanel.tsx`: add file upload control (PNG/JPEG, ≤10MB, convert to base64 data URI, show preview + remove button) visible when persona active
- [x] 3.6 Test: `setReferenceFaceUrl` / `clearReferenceFace` store actions (Jest)
- [x] 3.7 Test: `normalizeParameters` includes `image_url` for persona workflow (Jest)
