# Apply Progress: View 2 Frontend

## PR 1 / Phase 1: Foundation & Config
- ✅ 1.1 Create `/view2/package.json` — Next.js 16, React 19, Zustand, lucide-react, Vitest, Testing Library
- ✅ 1.2 Create `/view2/next.config.ts` — `/api/*` rewrites pointing to Modal backend
- ✅ 1.3 Create `/view2/tsconfig.json` — `@/` path alias, strict mode
- ✅ 1.4 Create `/view2/vitest.config.ts` — React plugin, jsdom, `@/` alias, `src/**/*.test.*`
- ✅ 1.5 Create `/view2/src/test/setup.ts` — mock `next/image`, import `@testing-library/jest-dom`
- ✅ 1.6 Copy `colors_and_type.css` from design system to `/view2/src/styles/`
- ✅ 1.7 Create `/view2/src/app/globals.css` — imports design tokens, minimal reset
- ✅ 1.8 Create `/view2/src/app/layout.tsx` — root layout, metadata, loads `globals.css`
- ✅ 1.9 Create `/view2/src/app/page.tsx` — renders `GenerationStudio` entry point (placeholder for now)
- ✅ 1.10 Verify: `npm install`, `tsc --noEmit`, `vitest run` pass

All tasks for Slice 1 are complete. The greenfield application has been successfully initialized and configured with the `ai-studio-design-system` tokens.

## PR 2 / Phase 2: State & Data Layer (TDD)
- ✅ 2.1 RED: Added failing Vitest coverage for backend-aligned types, API payloads/URLs/WS retry, generation store state machine, UI drawer store, and `useGenerationFlow` orchestration.
- ✅ 2.2 Created `/view2/src/features/generation/api/types.ts` with `JobEvent`, `GenerationState`, `WorkflowName`, and runtime enum arrays aligned to backend workflows/events.
- ✅ 2.3 Created `/view2/src/features/generation/api/client.ts` with `submitGenerate`, encoded `getWsUrl`/`getImageUrl`, and native WebSocket retry/backoff with cleanup.
- ✅ 2.4 Created `/view2/src/features/generation/stores/generationStore.ts` with prompt/parameter validation, backend event → frontend state mapping, job/session history, cleanup, and reference asset state.
- ✅ 2.5 Created `/view2/src/features/generation/stores/uiStore.ts` with `assetsDrawerOpen` and explicit open/close/toggle actions.
- ✅ 2.6 Created `/view2/src/features/generation/hooks/useGenerationFlow.ts` to orchestrate submit → WS → store event dispatch and workflow-specific reference payloads.
- ✅ 2.7 GREEN: `npm test -- --run` passed in `view2/` (24 tests). `npm run typecheck` also passed.

Strict TDD evidence:
- RED: initial `npm test -- --run` failed because `api/client`, `api/types`, `stores/generationStore`, `stores/uiStore`, and `hooks/useGenerationFlow` did not exist yet.
- GREEN: after minimal implementation, Vitest passed with mocked fetch/WebSocket coverage.

Slice 2 is complete. Phase 3 remains intentionally untouched per the selected slice boundary.

## PR 3 / Phase 3: UI Layout & Components (TDD)
- ✅ 3.1 RED: Added failing Vitest component coverage for `InputBar`, `WorkflowSelector`, `ChatSidebar`, `WorkspaceCanvas`, `AssetsDrawer`, and `GenerationStudio` before implementation. Initial RED failed on missing component imports.
- ✅ 3.2 Created component CSS Modules for layout geometry: panel widths, flex shells, drawer bounds, canvas sizing, and input/workflow geometry. Component modules use design tokens and contain no hardcoded color values.
- ✅ 3.3 Created `ChatSidebar.tsx` with message list, embedded `WorkflowSelector`, and embedded `InputBar`.
- ✅ 3.4 Created `InputBar.tsx` with textarea, pill send button, Enter-to-submit, Shift+Enter multiline support, and empty prompt validation.
- ✅ 3.5 Created `WorkflowSelector.tsx` with the three manual workflows and default `flux2_txt2img`.
- ✅ 3.6 Created `WorkspaceCanvas.tsx` with borderless workspace shell, artboard, status/progress indicator, result image, and error alert states.
- ✅ 3.7 Created `AssetsDrawer.tsx` with collapsible right panel, data-URL upload, gallery rendering, removal action, and 10MB limit guard.
- ✅ 3.8 Created `GenerationStudio.tsx` as the 3-panel root component and updated `/view2/src/app/page.tsx` to render it.
- ✅ 3.9 GREEN: `npm test -- --run` passed in `view2/` (39 tests). `npm run typecheck` also passed.

Strict TDD evidence:
- RED: initial `npm test -- --run` failed because all six requested component modules did not exist.
- GREEN: after minimal implementation, all component and existing state/client/hook tests passed.

Design-system correction:
- Replaced `/view2/src/styles/colors_and_type.css` with the canonical `Design  reference/ai-studio-design-system/colors_and_type.css` token/class contract because the previous copied file was the obsolete retro pixel design system and did not define `--color-bg-base`, `.btn`, `.input`, or `.surface-panel`.

Slice 3 is complete. Phase 4 remains intentionally untouched per the selected slice boundary.

## PR 4 / Phase 4: Integration & Polish
- ✅ 4.1 Wire `useGenerationFlow` hook into `GenerationStudio` and all child components
- ✅ 4.2 Connect `AssetsDrawer` upload → `generationStore.setReferenceFaceUrl` / `addToGallery`
- ✅ 4.3 Integration test: full cycle — prompt → generate → WS events → store → canvas renders
- ✅ 4.4 Verify `next build` succeeds with zero type errors
- ✅ 4.5 Run full `vitest run` — all tests green
- ✅ 4.6 Confirm zero retro pixel-art residue — no VT323, CRT scanlines, or pixel borders

All tasks for Slice 4 are complete. The greenfield application has been fully integrated and tests are passing.

## Verification Remediation: Critical Gaps Fixed (Strict TDD)

- ✅ Added Speed Selector next to Workflow Selector; Turbo maps to `generationStore.parameters.use_turbo = true`, Quality maps to `false`, and submissions include the selected value.
- ✅ Completed identity/reference validation UX: selecting `identidad_gguf` without an uploaded reference image shows exact error `Reference image required` and disables submission.
- ✅ Added `<1280px` responsive behavior: chat sidebar narrows to 280px and assets drawer auto-collapses via CSS media query.
- ✅ Corrected cold-start UI semantics: `booting_server` renders exact `Starting server...`, `downloading_weights` renders exact `Loading model weights...`, and progress is indeterminate until numeric progress arrives.

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| Speed selector | `src/features/generation/components/ChatSidebar.test.tsx`, `src/features/generation/components/GenerationStudio.integration.test.tsx`, `src/features/generation/stores/generationStore.test.ts` | Component + integration + unit | ✅ 18/18 relevant baseline tests passed | ✅ New tests failed on missing Speed selector / `use_turbo` wiring | ✅ Targeted suite 25/25 passed | ✅ Turbo default + Quality false submission | ✅ Kept selector localized in `ChatSidebar`, store normalization preserves `use_turbo` |
| Identity reference UX | `src/features/generation/components/InputBar.test.tsx`, `src/features/generation/components/GenerationStudio.integration.test.tsx`, `src/features/generation/stores/generationStore.test.ts` | Component + integration + unit | ✅ 18/18 relevant baseline tests passed | ✅ New tests failed because error was not surfaced/disabled and copy was mismatched | ✅ Targeted suite 25/25 passed | ✅ Store error copy + UI disable path | ✅ Reused `InputBar` validation path instead of adding duplicate banners |
| `<1280px` responsiveness | `src/features/generation/components/GenerationStudio.responsive.test.ts` | Static CSS contract | ✅ 18/18 relevant baseline tests passed | ✅ New CSS contract tests failed on missing media queries | ✅ Targeted suite 25/25 passed | ✅ Chat narrowing + drawer collapse assertions | ➖ None needed |
| Cold-start labels/progress | `src/features/generation/components/WorkspaceCanvas.test.tsx` | Component | ✅ 18/18 relevant baseline tests passed | ✅ New tests failed on old labels and determinate `0` progress | ✅ Targeted suite 25/25 passed | ✅ Booting + downloading states both covered | ✅ Extracted determinate flag for ARIA semantics |

### Verification

- ✅ RED run: targeted remediation suite failed as expected with 10 failing assertions before production changes.
- ✅ GREEN targeted run: `npm run test -- src/features/generation/components/ChatSidebar.test.tsx src/features/generation/components/InputBar.test.tsx src/features/generation/components/WorkspaceCanvas.test.tsx src/features/generation/components/GenerationStudio.integration.test.tsx src/features/generation/components/GenerationStudio.responsive.test.ts src/features/generation/stores/generationStore.test.ts` → 6 files / 25 tests passed.
- ✅ Full suite: `npx vitest run` → 13 files / 49 tests passed.
- ✅ Typecheck: `npm run typecheck` passed.

Known warning unchanged from verify report: `src/app/layout.test.tsx` still logs the existing `<html>` under `<div>` hydration warning, but the test passes.
