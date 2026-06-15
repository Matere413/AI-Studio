## Exploration: Frontend Architecture Restructure

### Current State

The frontend is a Next.js 16 app (App Router) located in `view/`. It is currently small—roughly 6 UI components, 1 API module, 1 Zustand store, and a handful of CSS modules—but already shows early signs of flat-folder technical debt.

**Key observations:**

- **Flat component bucket**: All UI lives in `src/components/studio/` regardless of whether it is a business-specific view (`Sidebar`, `Canvas`) or a generic UI primitive (`PixelProgressBar`).
- **Smart component anti-pattern**: `Sidebar.tsx` orchestrates the entire generation flow: form state, validation, HTTP POST, WebSocket connection, and retry logic. This mixes UI, business logic, and side effects in one file.
- **Store / API coupling**: `src/stores/generationStore.ts` knows about image URLs (`getImageUrl`) and holds a WebSocket cleanup function (`_wsCleanup`). `src/lib/api.ts` exports domain-specific helpers (`submitGenerate`, `getWsUrl`, `getImageUrl`, `connectWebSocket`) from a generic `lib` folder.
- **Co-located tests**: Tests are already co-located (good), but the `next/image` mock is copy-pasted across every component test. `ImageGallery.test.ts` is a non-TSX file that looks like a duplicate/typo.
- **Dead code**: `src/app/page.module.css` is a large boilerplate stylesheet from the Next.js template that is no longer used by the active page.

### Affected Areas

- `src/app/page.tsx` — thin entry point; will update import to the renamed layout component.
- `src/components/studio/*` — all 6 components + CSS modules + tests must be relocated.
- `src/lib/api.ts` — domain-specific API/WS code should move into the generation feature.
- `src/stores/generationStore.ts` — feature store should move into the generation feature.
- `src/styles/` — global tokens can stay, but CSS module imports inside components will need path updates.
- `vitest.config.ts` — no change needed; `@/*` alias already covers `src/`.
- All test files — imports and `vi.mock` paths must be updated.

### Approaches

#### 1. Conservative Layered Folders (Minimal)

Keep the existing `src/{components,lib,stores}/` buckets but add a `generation/` sub-folder inside each.

- `src/components/generation/...`
- `src/lib/generation/...`
- `src/stores/generation/...`
- `src/components/ui/...` for primitives

- **Pros**: Low friction, no new top-level folders, keeps the mental model close to standard Next.js.
- **Cons**: Still encourages buckets over domains; the Sidebar “smart component” problem is not solved by folder moves alone; every new feature adds another sub-folder inside three separate directories.
- **Effort**: Low

#### 2. Feature-First / Screaming Architecture (Recommended)

Introduce `src/features/` and `src/shared/` as top-level domains. Each feature owns its own API, components, hooks, stores, and types. Shared UI primitives and cross-cutting utilities live in `src/shared/`.

- **Pros**: Screams what the app does (`features/generation/` instead of `components/studio/`); natural boundaries for new features (inpainting, controlnet, etc.); the Sidebar can be split into a dumb UI component + a `useGenerationFlow` hook inside the same feature; keeps the codebase navigable as it grows.
- **Cons**: Slightly more folders for a 1-feature app; requires a single migration of imports.
- **Effort**: Medium

#### 3. Full “Clean Architecture” (Overkill)

Separate `application`, `domain`, `infrastructure`, and `presentation` layers.

- **Pros**: Maximum testability and inversion of control.
- **Cons**: Too much ceremony for a small UI layer; Next.js already handles routing/presentation; fighting the framework for marginal gains.
- **Effort**: High

### Recommendation

Adopt **Approach 2 — Feature-First / Screaming Architecture**.

Why:
- The user explicitly said the app is small *right now* and wants to fix structure before it grows. Feature-first is the most robust “small today, big tomorrow” pattern.
- The current `studio/` namespace is misleading; the real domain is **generation** (image generation). Renaming the folder to `features/generation/` makes the code match the product.
- Extracting `useGenerationFlow` from `Sidebar` immediately improves testability and makes the UI components pure presentational.

### Target Folder Structure

```
src/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   └── page.tsx
├── features/
│   └── generation/
│       ├── api/
│       │   ├── client.ts          (was src/lib/api.ts)
│       │   └── types.ts           (GenerationParameters, JobEvent, etc.)
│       ├── components/
│       │   ├── GenerationStudio.tsx  (was StudioLayout)
│       │   ├── PromptPanel.tsx       (was Sidebar)
│       │   ├── OutputCanvas.tsx      (was Canvas)
│       │   ├── SessionHistory.tsx    (was ImageGallery)
│       │   └── EventTerminal.tsx     (was TerminalLog)
│       ├── hooks/
│       │   └── useGenerationFlow.ts  (extract WS/API orchestration)
│       └── stores/
│           └── generationStore.ts
├── shared/
│   ├── components/
│   │   └── ui/
│   │       └── PixelProgressBar.tsx
│   └── styles/
│       ├── tokens.css              (was colors_and_type.css)
│       └── globals.css             (merge / keep separate)
└── test/
    └── setup.ts
```

### Migration Strategy

1. **Move (pure refactor, no logic changes)**
   - Create `features/generation/` and `shared/` trees.
   - Move `api.ts`, `generationStore.ts`, and components into the new homes.
   - Update all `import` paths from `@/components/studio/*`, `@/lib/api`, `@/stores/generationStore` to the new locations.
   - Move CSS modules alongside their components.
   - Delete `src/app/page.module.css` (dead code).

2. **Extract hook (single business-logic refactor)**
   - Move the `handleGenerate` / `handleCancel` / WebSocket orchestration out of `PromptPanel.tsx` into `features/generation/hooks/useGenerationFlow.ts`.
   - `PromptPanel.tsx` becomes a presentational component that receives callbacks and state via props.
   - `GenerationStudio.tsx` wires the hook to the panel.

3. **Tests**
   - Move tests to mirror the new file paths.
   - Replace per-file `vi.mock("next/image")` with a single global mock in `src/test/setup.ts`.
   - Verify `vitest` suite passes after each move.

4. **Review guard**
   - The entire change is a refactor; there are zero behavior changes.
   - To keep the PR under the 400-line review budget, the work can be delivered as a single PR if the diff is mostly file renames (GitHub tracks renames with low cognitive load). If the diff appears as many deletions + additions, split into two chained PRs: (a) Move files, (b) Extract hook + cleanup.

### Risks

- **Import churn**: `tsconfig.json` `@/*` alias covers the new paths, so imports only change directory segments. Risk is low.
- **next/image mock duplication**: Currently copy-pasted in 4 tests. If not centralized during the move, the copy-paste tax continues.
- **Dead CSS**: `page.module.css` is unused. If left behind, it becomes a ghost file.
- **Review size**: A full restructure can touch ~15 files. If GitHub does not detect renames, the diff will look large. Mitigate by splitting into two chained PRs (Move, then Refactor).

### Ready for Proposal

**Yes.** The current architecture is simple enough to map cleanly to a feature-first structure. The orchestrator should tell the user that the plan is to move the flat `components/studio/` bucket into a `features/generation/` domain, extract the generation orchestration hook out of the sidebar, and promote `PixelProgressBar` to shared UI. The next step is `sdd-propose` to formalize the scope, rollback plan, and delivery strategy.
