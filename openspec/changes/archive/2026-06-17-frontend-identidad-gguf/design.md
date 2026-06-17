# Design: Frontend Identidad GGUF

## Technical Approach

Add `identidad_gguf` to workflow types, compose `IdentitySettingsPanel` below `PromptPanel` in the `GenerationStudio` sidebar, extend the Zustand store with session-scoped gallery and identity-specific validation, and create a canvas-based image resize utility for uploads >5MB. Payload construction stays in `useGenerationFlow.generate()` — `image_url` only for `identidad_gguf` (existing `realistic_persona` behavior unchanged).

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| Panel placement | Extend PromptPanel inline vs. separate component | **Separate `IdentitySettingsPanel` composed in `GenerationStudio` sidebar** | PromptPanel already 560 lines with workflow-conditionals. Isolating identity UX prevents further bloat and follows feature-first structure. |
| Gallery storage | Zustand store vs. component state | **`referenceGallery: string[]` in store** | Same pattern as `referenceFaceUrl`; enables session-scoped persistence and the panel reads from store on mount. |
| Image upload >5MB | Browser-native resize vs. server-side | **Canvas-based `imageResize.ts` utility** | Proposal bans crop tool; client-side canvas scaling to 1024px max dimension with JPEG quality 0.8 avoids extra HTTP round-trip. |
| Payload construction | client.ts filter vs. hook-level conditional | **`useGenerationFlow.generate()` constructs `submissionParameters`** | Existing pattern — `realistic_persona` already does this at line 33-36. Keeps API client domain-agnostic. |

## Data Flow

```
User clicks gallery thumbnail  ──→ setReferenceFaceUrl(url)
User uploads file               ──→ resizeImageIfNeeded() → FileReader → setReferenceFaceUrl(dataURL)
                                         │                          │
                                         └── addToGallery(dataURL) ─┘
                                               │
                                     ValidationErrors.referenceImage ← workflow==="identidad_gguf" && !referenceFaceUrl
                                               │
Generate click ──→ useGenerationFlow.generate()
                         │
               workflow === "identidad_gguf" && referenceFaceUrl
                         │  YES: submissionParameters.image_url = referenceFaceUrl
                         │  NO:  image_url excluded
                         ▼
               submitGenerate(prompt, submissionParameters) → POST /api/generate
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `view/src/features/generation/api/types.ts` | Modify | Add `"identidad_gguf"` to `WorkflowName`. Add `referenceImage?` to `ValidationErrors`. |
| `view/src/features/generation/stores/generationStore.ts` | Modify | Add `"identidad_gguf"` to `VALID_WORKFLOWS`. Add `referenceGallery`, `addToGallery`. Add `identidad_gguf` case in `normalizeParameters`. Add identity validation in `validateParameters`. |
| `view/src/features/generation/hooks/useGenerationFlow.ts` | Modify | Expose `addToGallery`. Construct payload with `image_url` for `identidad_gguf`. |
| `view/src/features/generation/components/GenerationStudio.tsx` | Modify | Import and render `IdentitySettingsPanel` below `PromptPanel` in sidebar. |
| `view/src/features/generation/components/IdentitySettingsPanel.tsx` | Create | Gallery grid, upload button with validation, preview thumbnail, disabled overlay with warning text. Receives `flow: GenerationFlowViewModel`. |
| `view/src/features/generation/components/IdentitySettingsPanel.module.css` | Create | CSS module using Matere tokens: `--space-*`, `--border-*`, `--fg-muted`, `--accent`, `--font-pixel`, `--font-sans`. |
| `view/src/features/generation/utils/imageResize.ts` | Create | `resizeImageIfNeeded(file: File, maxBytes?: number): Promise<Blob>`. Canvas to 1024px max dimension, JPEG quality 0.8. Passes files ≤5MB unchanged, compresses 5–10MB, rejects >10MB. |
| `view/src/features/generation/api/client.ts` | Modify | Remove unconditional `image_url` from payload; delegate inclusion to hook-level submission parameters. |

## Interfaces / Contracts

```typescript
// Extended workflow type
type WorkflowName = /* existing... */ | "identidad_gguf";

// Extended validation errors
interface ValidationErrors {
  prompt?: string;
  parameters?: string;
  referenceImage?: string;  // "Reference image is required"
}

// Image resize utility signature
function resizeImageIfNeeded(file: File, maxBytes?: number): Promise<Blob>;
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `resizeImageIfNeeded` — <5MB passthrough, 5–10MB compresses, >10MB rejects | Vitest + canvas mock |
| Unit | `validateParameters` — identidad_gguf requires reference, other workflows do not | Vitest (extend `generationStore.test.ts`) |
| Integration | `IdentitySettingsPanel` — gallery render, upload flow, disabled state, warning text | @testing-library/react, mock FileReader |
| Integration | `GenerationStudio` — renders IdentitySettingsPanel when identidad_gguf active | @testing-library/react |

## Migration / Rollout

No migration required. `identidad_gguf` is additive — existing workflows and store shape unchanged.

## Open Questions

None. All architectural decisions resolved with clear rationale above.
