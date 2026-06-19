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
