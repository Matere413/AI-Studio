# Design: Frontend Architecture Restructure

## Technical Approach

Perform a behavior-preserving frontend refactor in two safe slices: first move files into feature-first boundaries and update imports, then extract generation orchestration from the current `Sidebar` smart component into a feature hook. Runtime behavior stays unchanged: `/api/generate`, `/api/ws/generate/{jobId}`, retry handling, store transitions, and generated previews loaded from `/api/images/{jobId}` remain the contracts.

Target structure:

```text
view/src/
├── app/page.tsx
├── features/generation/
│   ├── api/{client.ts,types.ts,client.test.ts,client-ws.test.ts}
│   ├── components/{GenerationStudio,PromptPanel,OutputCanvas,SessionHistory,EventTerminal}.tsx
│   ├── hooks/useGenerationFlow.ts
│   └── stores/generationStore.ts
├── shared/components/ui/PixelProgressBar.tsx
├── styles/{colors_and_type.css,portfolio.css}
└── test/setup.ts
```

`features/generation/` owns generation-specific UI, API contracts, WebSocket orchestration, Zustand state, types, CSS modules, and tests. `shared/` contains reusable, domain-agnostic UI only; in this slice that is `PixelProgressBar`. Global design-system CSS remains in `view/src/styles/` to avoid unrelated churn.

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Feature-first `features/generation/` vs layered `components/lib/stores` buckets | Slightly more folders now, clearer growth path later | Use feature-first because the app is expected to grow and the real domain is generation. |
| Extract `useGenerationFlow` vs keep orchestration in `PromptPanel` | One new hook, less smart UI | Extract HTTP submit, WS connect, retry exhaustion, and cleanup storage into `useGenerationFlow`; keep `PromptPanel` presentational. |
| Full Clean Architecture | Stronger layering, too much ceremony for one small frontend feature | Do not introduce domain/application/infrastructure layers yet. |
| Move global CSS into `shared/styles` | More churn without behavior benefit | Keep `view/src/styles/`; only reusable components move to `shared`. |

## Data Flow

```text
app/page.tsx
  └─ GenerationStudio
      ├─ PromptPanel ──generate/cancel/reset──→ useGenerationFlow
      │                                      ├─ submitGenerate('/api/generate')
      │                                      ├─ startConnecting(jobId)
      │                                      └─ connectWebSocket('/api/ws/generate/{jobId}')
      ├─ OutputCanvas  ←────────────── useGenerationStore
      ├─ SessionHistory ←───────────── useGenerationStore
      └─ EventTerminal ←────────────── useGenerationStore

WebSocket event → generationStore.addEvent → completed → imagePath '/api/images/{jobId}' → Next Image preview
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `view/src/app/page.tsx` | Modify | Import `GenerationStudio` from the feature. |
| `view/src/lib/api.ts` | Move | Becomes `features/generation/api/client.ts`. |
| `view/src/features/generation/api/types.ts` | Create | Holds `GenerationParameters`, `JobEvent`, store-facing generation types. |
| `view/src/stores/generationStore.ts` | Move/Modify | Move into feature; keep state contract and `/api/images/{jobId}` history behavior. |
| `view/src/components/studio/StudioLayout.tsx` | Move/Rename | `features/generation/components/GenerationStudio.tsx`. |
| `view/src/components/studio/Sidebar.tsx` | Move/Rename/Modify | `PromptPanel.tsx`; receives state/callbacks from hook. |
| `view/src/components/studio/Canvas.tsx` | Move/Rename | `OutputCanvas.tsx`; import shared progress bar. |
| `view/src/components/studio/ImageGallery.tsx` | Move/Rename | `SessionHistory.tsx`. |
| `view/src/components/studio/TerminalLog.tsx` | Move/Rename | `EventTerminal.tsx`. |
| `view/src/components/studio/PixelProgressBar.tsx` | Move | `shared/components/ui/PixelProgressBar.tsx`. |
| `*.module.css` and tests | Move/Modify | Keep co-located with renamed components; update imports/mocks. |
| `view/src/test/setup.ts` | Modify | Centralize `next/image` mock used by component tests. |
| `view/src/app/page.module.css` and `ImageGallery.test.ts` | Delete | Remove unused template CSS and duplicate non-TSX test. |

## Interfaces / Contracts

- `useGenerationFlow()` returns the PromptPanel view model: prompt, parameters, validation errors, derived booleans, and `generate`, `cancel`, `reset`, `setPrompt`, `setParameters` callbacks.
- API client contracts stay equivalent: `submitGenerate(prompt, params)`, `getWsUrl(jobId)`, `getImageUrl(jobId)`, `connectWebSocket(url, options)`.
- Store selectors and actions keep their current names to minimize component/test churn.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | API payloads, WS retry/cleanup, store transitions, `useGenerationFlow` orchestration | Move existing tests, add hook tests with mocked API client. Run `npm exec vitest -- --run` because `package.json` has no test script. |
| Component | Prompt validation, canvas preview, session history, terminal, progress bar | Move co-located tests; centralize `next/image` mock in `src/test/setup.ts`. |
| Integration | `GenerationStudio` composition | Keep layout composition test with updated imports and no visual/behavior changes. |
| E2E | Not currently present | No new E2E layer for this refactor. |

## Migration / Rollout

No runtime migration required. This is a source-level refactor only; no persisted data, backend endpoint, WebSocket protocol, image URL, or user-visible behavior changes.

## Open Questions

None.
