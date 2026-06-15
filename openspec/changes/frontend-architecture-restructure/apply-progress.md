# Apply Progress: Frontend Architecture Restructure

## Batch

- Current work unit: 2 / PR 2 — hook extraction + documentation
- Strategy: feature-branch-chain
- Tracker branch: `feat/frontend-architecture-restructure`
- PR 1 branch: `feat/frontend-architecture-restructure-pr1`
- PR 2 branch: `feat/frontend-architecture-restructure-pr2`
- Worktree: `/Users/matere/Documents/Proyectos Programados/AI-Studio.worktrees/frontend-architecture-restructure-pr1`
- PR boundary: PR 2 builds on PR 1 and should later target `feat/frontend-architecture-restructure-pr1`, not `main`.

## Completed Tasks

- [x] 1.1 Create git worktree at separate path for implementation isolation
- [x] 1.2 Create dirs: `features/generation/{api,components,hooks,stores}`, `shared/components/ui/`
- [x] 1.3 Create `features/generation/api/types.ts` — GenerationParameters, JobEvent, WS event types
- [x] 1.4 Move `PixelProgressBar.tsx` + CSS + test → `shared/components/ui/`
- [x] 1.5 Centralize `next/image` mock in `src/test/setup.ts`
- [x] 2.1 Move `api.ts` → `features/generation/api/client.ts`; update WS/HTTP exports
- [x] 2.2 Move `api.test.ts` + `api-ws.test.ts` → `features/generation/api/`
- [x] 2.3 Move `generationStore.ts` + test → `features/generation/stores/`
- [x] 2.4 Rename/move components: StudioLayout→GenerationStudio, Sidebar→PromptPanel, Canvas→OutputCanvas, ImageGallery→SessionHistory, TerminalLog→EventTerminal
- [x] 2.5 Move/rename co-located CSS modules and tests for renamed components
- [x] 2.6 Update `page.tsx` import to `features/generation/components/GenerationStudio`
- [x] 2.7 Delete unused `page.module.css` and duplicate `ImageGallery.test.ts`
- [x] 3.1 [RED] Write failing tests for `useGenerationFlow` (submit, cancel, reset, WS lifecycle, retry exhaustion)
- [x] 3.2 [GREEN] Extract `useGenerationFlow` in `features/generation/hooks/` — HTTP submit, WS connect/retry/cleanup from Sidebar
- [x] 3.3 [REFACTOR] Convert Sidebar→PromptPanel to receive view model; remove old orchestration
- [x] 3.4 Verify existing component tests pass with new hook wiring
- [x] 4.1 Run `npm exec vitest -- --run`; fix all import/mock issues
- [x] 4.2 Verify behavior preservation per spec: generation submit, WS lifecycle, state transitions, preview, validation, gallery
- [x] 5.1 Update `view/AGENTS.md` with new frontend architecture folder conventions

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | Existing suite | Structural | ✅ 90/90 baseline after dependency install | N/A — worktree setup only | ✅ Worktree created | ➖ Structural only | ➖ None needed |
| 1.2 | Existing suite | Structural | ✅ 90/90 baseline | N/A — directory creation only | ✅ Target folders created | ➖ Structural only | ➖ None needed |
| 1.3 | `src/features/generation/api/client.test.ts`, `src/features/generation/stores/generationStore.test.ts` | Unit | ✅ Existing API/store tests preserved | N/A — type relocation for existing behavior | ✅ 85/85 final in PR 1 | ➖ Type-only extraction | ✅ Shared generation types centralized |
| 1.4 | `src/shared/components/ui/PixelProgressBar.test.tsx` | Component | ✅ Existing progress bar tests preserved | N/A — move-only | ✅ 7/7 progress bar tests | ➖ Move-only | ✅ Shared UI import updated |
| 1.5 | Component tests using `next/image` | Component | ✅ Existing duplicate mocks passed before move | N/A — test infrastructure refactor | ✅ 85/85 final in PR 1 | ➖ Mock setup only | ✅ `next/image` mock centralized in `src/test/setup.ts` |
| 2.1 | `src/features/generation/api/client.test.ts`, `src/features/generation/api/client-ws.test.ts` | Unit | ✅ Existing API tests preserved | N/A — move-only | ✅ 11/11 API tests | ✅ HTTP + WS cases preserved | ✅ Imports updated to feature-local types |
| 2.2 | `src/features/generation/api/client.test.ts`, `src/features/generation/api/client-ws.test.ts` | Unit | ✅ Existing API tests preserved | N/A — move-only | ✅ 11/11 API tests | ➖ Move-only | ✅ Test imports updated |
| 2.3 | `src/features/generation/stores/generationStore.test.ts` | Unit | ✅ Existing store tests preserved | N/A — move-only | ✅ 26/26 store tests | ✅ Store state/history cases preserved | ✅ Store re-exports type contract |
| 2.4 | Component test suite | Component | ✅ Existing component tests preserved | N/A — move/rename only | ✅ 41/41 component tests | ✅ Prompt, canvas, history, terminal cases preserved | ✅ Component imports renamed |
| 2.5 | Component test suite | Component | ✅ Existing component/CSS module tests preserved | N/A — move-only | ✅ 41/41 component tests | ➖ CSS/test relocation only | ✅ Co-located CSS modules/tests retained |
| 2.6 | `src/features/generation/components/GenerationStudio.test.tsx` | Integration | ✅ Existing layout composition tests preserved | N/A — import update only | ✅ 6/6 layout tests | ✅ Layout composition still renders | ✅ `app/page.tsx` imports feature entry |
| 2.7 | Final suite | Cleanup | ✅ Existing duplicate utility test existed before cleanup | N/A — delete unused/duplicate files | ✅ 85/85 final in PR 1 | ➖ Cleanup only | ✅ Duplicate non-TSX gallery test removed |
| 3.1 | `src/features/generation/hooks/useGenerationFlow.test.tsx` | Unit/hook | ✅ 19/19 PromptPanel + GenerationStudio baseline | ✅ Import failed because `useGenerationFlow` did not exist | ✅ 7/7 hook tests passing | ✅ 7 cases: submit, submit failure, completed event preview, retry exhaustion, cancel, reset, invalid submit | ✅ Mock completed-event path fixed to include `getImageUrl`; review warning covered submit rejection |
| 3.2 | `src/features/generation/hooks/useGenerationFlow.test.tsx` | Unit/hook | ✅ 19/19 baseline | ✅ Hook tests written first | ✅ 7/7 hook tests passing | ✅ Payload, submit failure, WS options, cleanup, store transitions covered | ✅ Orchestration isolated in hook |
| 3.3 | `src/features/generation/components/PromptPanel.test.tsx`, `src/features/generation/components/GenerationStudio.test.tsx` | Component/integration | ✅ 19/19 baseline before refactor | ✅ Approval coverage existed before production refactor | ✅ 25/25 hook + component tests passing | ✅ PromptPanel submit + GenerationStudio composition exercised | ✅ PromptPanel now receives `GenerationFlowViewModel` from `GenerationStudio` |
| 3.4 | Hook + component focused suite | Verification | ✅ 19/19 baseline | ✅ Existing behavior tests exercised new wiring | ✅ 25/25 focused tests passing | ✅ Hook, PromptPanel, and GenerationStudio covered together | ✅ Full suite also passed 91/91 |
| 4.1 | Full frontend suite | Verification | ✅ 90/90 baseline in PR 1 | N/A — verification task | ✅ 91/91 final in PR 2 | ✅ All feature test layers exercised | ✅ Import/mock issues fixed |
| 4.2 | Full frontend suite | Verification | ✅ Behavior baseline captured | N/A — verification task | ✅ 91/91 final in PR 2 | ✅ Submit, WS, state, preview, validation, gallery covered | ✅ Hook extraction preserves behavior |
| 5.1 | `view/AGENTS.md` | Documentation | ✅ Full suite unaffected before docs update | N/A — documentation-only convention update | ✅ 91/91 full suite after update | ➖ Triangulation skipped: single documentation outcome | ✅ Conventions chunked into scannable architecture table |

## Verification Results

| Command | Result |
|---------|--------|
| `npx vitest run src/features/generation/components/PromptPanel.test.tsx src/features/generation/components/GenerationStudio.test.tsx` from `view/` before PR 2 changes | ✅ 2 files, 19 tests passed |
| `npx vitest run src/features/generation/hooks/useGenerationFlow.test.tsx` from `view/` after RED test write | ✅ Failed as expected: unresolved `./useGenerationFlow` import |
| `npx vitest run src/features/generation/hooks/useGenerationFlow.test.tsx` from `view/` after hook implementation and review warning remediation | ✅ 1 file, 7 tests passed |
| `npx vitest run src/features/generation/hooks/useGenerationFlow.test.tsx src/features/generation/components/PromptPanel.test.tsx src/features/generation/components/GenerationStudio.test.tsx` from `view/` after component refactor | ✅ 3 files, 25 tests passed |
| `npx vitest run` from `view/` after review warning remediation | ✅ 10 files, 92 tests passed |

The final count is higher than PR 1 because `useGenerationFlow.test.tsx` adds seven hook tests, including submit rejection coverage.

## Notes

- Work Unit 2 extracts HTTP submit, WebSocket connect/retry exhaustion callback, event forwarding, cancel cleanup, and reset cleanup into `useGenerationFlow`.
- `PromptPanel` is now presentational and receives a `GenerationFlowViewModel`; `GenerationStudio` owns the hook invocation and passes the view model down.
- `view/AGENTS.md` now documents feature-first generation boundaries, shared UI placement, thin app routes, and global style placement.
- A requested Next.js docs path (`node_modules/next/dist/docs/`) was not present in this installed Next.js package when checked.
- Review warning remediation added focused submit rejection coverage proving the hook transitions to `error` with the rejection message and does not open a WebSocket.

## Remaining Tasks

- None. All 19 planned tasks are checked in `tasks.md`; verification/report/archive remain separate SDD phases.
