# Tasks: Frontend Identidad GGUF

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~465 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Foundation → PR 2: UI |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

```
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: Medium
```

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Types, store, resize utility + tests | PR 1 | Base: main. Verification included per work unit. |
| 2 | IdentitySettingsPanel, CSS, flow integration + tests | PR 2 | Base: main or PR 1 branch if chained. Depends on PR 1 types. |

## Phase 1: Foundation — Types, Store, Utility

- [x] 1.1 Add `"identidad_gguf"` to `WorkflowName` union and `referenceImage?` to `ValidationErrors` in `api/types.ts`
- [x] 1.2 Add `referenceGallery`, `addToGallery`, identidad_gguf `normalizeParameters` case, and identity validation in `stores/generationStore.ts`
- [x] 1.3 Create `utils/imageResize.ts` — `resizeImageIfNeeded()` canvas to 1024px max, JPEG q0.8, <5MB passthrough, >10MB reject
- [x] 1.4 Add identidad_gguf store validation and gallery tests to `stores/generationStore.test.ts`
- [x] 1.5 Add resize utility unit tests to `utils/imageResize.test.ts`

## Phase 2: UI — IdentitySettingsPanel and Integration

- [x] 2.1 Create `IdentitySettingsPanel.tsx` — gallery grid, upload button, preview thumbnail, disabled overlay, warning text
- [x] 2.2 Create `IdentitySettingsPanel.module.css` — gallery grid, disabled state, Matere design tokens
- [x] 2.3 Render `IdentitySettingsPanel` below `PromptPanel` in `GenerationStudio.tsx`
- [x] 2.4 Expose `addToGallery` and add identidad_gguf `image_url` payload logic in `hooks/useGenerationFlow.ts`
- [x] 2.5 Delegate `image_url` inclusion from `client.ts` to hook-level `submissionParameters`
- [x] 2.6 Add component tests for gallery, upload, disabled, warning states in `IdentitySettingsPanel.test.tsx`
- [x] 2.7 Add identidad_gguf payload inclusion/exclusion tests in `hooks/useGenerationFlow.test.tsx`
- [x] 2.8 Verify `IdentitySettingsPanel` renders in `GenerationStudio.test.tsx`
