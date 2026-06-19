# Tasks: View 2 Frontend Rebuild

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 2500–3500 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (State) → PR 3 (UI) → PR 4 (Integration) |
| Delivery strategy | ask-always |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units (feature-branch-chain)

| Unit | Goal | Likely PR | Base Branch |
|------|------|-----------|-------------|
| 1 | Next.js scaffold + Vitest + design tokens | PR 1 | feature/view2-rebuild |
| 2 | Types, client, stores, useGenerationFlow with TDD | PR 2 | PR 1 branch |
| 3 | All 5 UI components with unit tests | PR 3 | PR 2 branch |
| 4 | Wire UI to stores, integration tests, verify build | PR 4 | PR 3 branch |

## Phase 1: Foundation & Config

- [x] 1.1 Create `/view2/package.json` — Next.js 16, React 19, Zustand, lucide-react, Vitest, Testing Library
- [x] 1.2 Create `/view2/next.config.ts` — `/api/*` rewrites pointing to Modal backend
- [x] 1.3 Create `/view2/tsconfig.json` — `@/` path alias, strict mode
- [x] 1.4 Create `/view2/vitest.config.ts` — React plugin, jsdom, `@/` alias, `src/**/*.test.*`
- [x] 1.5 Create `/view2/src/test/setup.ts` — mock `next/image`, import `@testing-library/jest-dom`
- [x] 1.6 Copy `colors_and_type.css` from design system to `/view2/src/styles/`
- [x] 1.7 Create `/view2/src/app/globals.css` — imports design tokens, minimal reset
- [x] 1.8 Create `/view2/src/app/layout.tsx` — root layout, metadata, loads `globals.css`
- [x] 1.9 Create `/view2/src/app/page.tsx` — renders `GenerationStudio` entry point
- [x] 1.10 Verify: `npm install`, `tsc --noEmit`, `vitest run` pass

## Phase 2: State & Data Layer (TDD)

- [x] 2.1 RED: Write failing tests for types, client, and stores
- [x] 2.2 Create `api/types.ts` — `JobEvent`, `GenerationState`, `WorkflowName`, aligned to backend enum
- [x] 2.3 Create `api/client.ts` — `submitGenerate`, `getWsUrl`, `getImageUrl`, `connectWebSocket` with retry
- [x] 2.4 Create `stores/generationStore.ts` — prompt, params, job, state machine, validation, reference assets
- [x] 2.5 Create `stores/uiStore.ts` — `assetsDrawerOpen` toggle actions
- [x] 2.6 Create `hooks/useGenerationFlow.ts` — submit → WS → store orchestration
- [x] 2.7 GREEN: All store/client/hook tests pass with mocked fetch and WS

## Phase 3: UI Layout & Components (TDD)

- [x] 3.1 RED: Write failing tests for each component (render + interaction scenarios)
- [x] 3.2 Create CSS Module files per component for layout geometry (panel widths, flex, bounds)
- [x] 3.3 Create `ChatSidebar.tsx` — message list + embeds InputBar and WorkflowSelector
- [x] 3.4 Create `InputBar.tsx` — textarea + send button, Enter submit, empty prompt validation
- [x] 3.5 Create `WorkflowSelector.tsx` — dropdown for 3 workflows, defaults to `flux2_txt2img`
- [x] 3.6 Create `WorkspaceCanvas.tsx` — artboard, progress indicator, result image, error banner
- [x] 3.7 Create `AssetsDrawer.tsx` — collapsible right panel, upload/gallery/remove, 10MB limit
- [x] 3.8 Create `GenerationStudio.tsx` — 3-panel root: ChatSidebar + WorkspaceCanvas + AssetsDrawer
- [x] 3.9 GREEN: All component tests pass with design-system class assertions

## Phase 4: Integration & Polish

- [x] 4.1 Wire `useGenerationFlow` hook into `GenerationStudio` and all child components
- [x] 4.2 Connect `AssetsDrawer` upload → `generationStore.setReferenceFaceUrl` / `addToGallery`
- [x] 4.3 Integration test: full cycle — prompt → generate → WS events → store → canvas renders
- [x] 4.4 Verify `next build` succeeds with zero type errors
- [x] 4.5 Run full `vitest run` — all tests green
- [x] 4.6 Confirm zero retro pixel-art residue — no VT323, CRT scanlines, or pixel borders
