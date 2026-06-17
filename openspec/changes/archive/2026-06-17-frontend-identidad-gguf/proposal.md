# Proposal: Frontend Identidad GGUF

## Intent

Add a Matere-native identity UX for `identidad_gguf`: users choose or upload a reference face before submitting `workflow="identidad_gguf"`, `prompt`, and `image_url`.

## Scope

### In Scope
- Add `identidad_gguf` to frontend workflow selection and request typing.
- Add lateral Identity Settings panel with gallery, upload, preview, disabled state, and warning.
- Preserve Matere Design System: Apple-inspired spacing, existing UI primitives, feature components, and CSS modules.

### Out of Scope
- Backend, Modal, model/cache changes.
- Account-level persona management or persisted user galleries.
- Advanced face detection or automatic face quality scoring.
- Image cropping tools in the frontend (users must upload pre-cropped images).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `generative-ai-studio-frontend`: Add identity workflow selection, lateral settings, gallery/upload source choice, disabled non-applicable state, and `image_url` payload behavior.
- `identity-gguf-workflows`: Clarify that `image_url` may be URL or base64/data URL.

## Approach

Keep prompt primary. Compose a lateral identity panel from `GenerationStudio` using feature components plus shared primitives. Store selected image in the generation store, include it only for `identidad_gguf`, and keep the preview grayed with “Not applicable for this workflow” elsewhere.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `view/src/features/generation/components/GenerationStudio.tsx` | Modified | Compose lateral identity panel. |
| `view/src/features/generation/components/*Identity*` | New | Selector, gallery, upload, warning, preview. |
| `view/src/features/generation/stores/generationStore.ts` | Modified | Track identity selection and workflow-aware payload state. |
| `view/src/features/generation/api/types.ts` | Modified | Add `identidad_gguf` workflow typing. |
| `view/src/features/generation/api/client.ts` | Modified | Send `image_url` only when applicable. |
| `view/src/shared/components/ui/` | Modified | Reuse existing dialog/panel primitives. |
| `openspec/specs/*` | Modified | Delta specs for frontend and identity contract. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Disabled preview confuses users | Medium | Add clear warning copy and disabled affordance. |
| Base64 payload size hurts requests | Low | Enforce max size validation and auto-compress before storing. |

## Rollback Plan

Revert identity panel, store/type changes, and spec deltas. Existing workflows keep current behavior; no data migration.

## Dependencies

- Existing `identidad_gguf` manifest and `/generate` routing.
- Existing Matere CSS modules and shared UI primitives.

## Success Criteria

- [ ] `identidad_gguf` cannot submit without prompt plus selected reference image.
- [ ] Upload and gallery paths both produce an `image_url` payload.
- [ ] Non-identity workflows show the image disabled with warning, without clearing it.
- [ ] UI follows Matere Design System and frontend tests/type checks pass.