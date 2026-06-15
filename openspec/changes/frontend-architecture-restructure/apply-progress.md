# Apply Progress: Frontend Architecture Restructure

## Batch

- Work unit: 1 / PR 1 — move-only frontend restructure
- Strategy: feature-branch-chain
- Tracker branch: `feat/frontend-architecture-restructure`
- PR 1 branch: `feat/frontend-architecture-restructure-pr1`
- Worktree: `/Users/matere/Documents/Proyectos Programados/AI-Studio.worktrees/frontend-architecture-restructure-pr1`

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
- [x] 4.1 Run `npm exec vitest -- --run`; fix all import/mock issues
- [x] 4.2 Verify behavior preservation per spec: generation submit, WS lifecycle, state transitions, preview, validation, gallery

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | Existing suite | Structural | ✅ 90/90 baseline after dependency install | N/A — worktree setup only | ✅ Worktree created | ➖ Structural only | ➖ None needed |
| 1.2 | Existing suite | Structural | ✅ 90/90 baseline | N/A — directory creation only | ✅ Target folders created | ➖ Structural only | ➖ None needed |
| 1.3 | `src/features/generation/api/client.test.ts`, `src/features/generation/stores/generationStore.test.ts` | Unit | ✅ Existing API/store tests preserved | N/A — type relocation for existing behavior | ✅ 85/85 final | ➖ Type-only extraction | ✅ Shared generation types centralized |
| 1.4 | `src/shared/components/ui/PixelProgressBar.test.tsx` | Component | ✅ Existing progress bar tests preserved | N/A — move-only | ✅ 7/7 progress bar tests | ➖ Move-only | ✅ Shared UI import updated |
| 1.5 | Component tests using `next/image` | Component | ✅ Existing duplicate mocks passed before move | N/A — test infrastructure refactor | ✅ 85/85 final | ➖ Mock setup only | ✅ `next/image` mock centralized in `src/test/setup.ts` |
| 2.1 | `src/features/generation/api/client.test.ts`, `src/features/generation/api/client-ws.test.ts` | Unit | ✅ Existing API tests preserved | N/A — move-only | ✅ 11/11 API tests | ✅ HTTP + WS cases preserved | ✅ Imports updated to feature-local types |
| 2.2 | `src/features/generation/api/client.test.ts`, `src/features/generation/api/client-ws.test.ts` | Unit | ✅ Existing API tests preserved | N/A — move-only | ✅ 11/11 API tests | ➖ Move-only | ✅ Test imports updated |
| 2.3 | `src/features/generation/stores/generationStore.test.ts` | Unit | ✅ Existing store tests preserved | N/A — move-only | ✅ 26/26 store tests | ✅ Store state/history cases preserved | ✅ Store re-exports type contract |
| 2.4 | Component test suite | Component | ✅ Existing component tests preserved | N/A — move/rename only | ✅ 41/41 component tests | ✅ Prompt, canvas, history, terminal cases preserved | ✅ Component imports renamed |
| 2.5 | Component test suite | Component | ✅ Existing component/CSS module tests preserved | N/A — move-only | ✅ 41/41 component tests | ➖ CSS/test relocation only | ✅ Co-located CSS modules/tests retained |
| 2.6 | `src/features/generation/components/GenerationStudio.test.tsx` | Integration | ✅ Existing layout composition tests preserved | N/A — import update only | ✅ 6/6 layout tests | ✅ Layout composition still renders | ✅ `app/page.tsx` imports feature entry |
| 2.7 | Final suite | Cleanup | ✅ Existing duplicate utility test existed before cleanup | N/A — delete unused/duplicate files | ✅ 85/85 final | ➖ Cleanup only | ✅ Duplicate non-TSX gallery test removed |
| 4.1 | Full frontend suite | Verification | ✅ 90/90 baseline | N/A — verification task | ✅ 85/85 final | ✅ All moved test layers exercised | ✅ Import/mock issues fixed |
| 4.2 | Full frontend suite | Verification | ✅ Behavior baseline captured | N/A — verification task | ✅ 85/85 final | ✅ Submit, WS, state, preview, validation, gallery covered | ✅ No hook extraction performed |

## Verification Results

| Command | Result |
|---------|--------|
| `npm exec vitest -- --run` from `view/` before moves | ✅ 10 files, 90 tests passed |
| `npm exec vitest -- --run` from `view/` after moves | ✅ 9 files, 85 tests passed |

The final count is lower because the duplicate non-TS `ImageGallery.test.ts` was removed as specified by task 2.7; behavior coverage remains in `SessionHistory.test.tsx`.

## Notes

- No `useGenerationFlow` hook extraction was implemented in this batch.
- No `AGENT.md`/`AGENTS.md` documentation update was implemented in this batch.
- The worktree was created from committed `master`; the active original checkout had uncommitted frontend baseline files and ignored `view/src/lib/*` API files. Those frontend baseline files were copied into the worktree so PR 1 could apply the requested move-only slice without editing the original checkout.

## Remaining Tasks

- [ ] 3.1 [RED] Write failing tests for `useGenerationFlow` (submit, cancel, reset, WS lifecycle, retry exhaustion)
- [ ] 3.2 [GREEN] Extract `useGenerationFlow` in `features/generation/hooks/` — HTTP submit, WS connect/retry/cleanup from Sidebar
- [ ] 3.3 [REFACTOR] Convert Sidebar→PromptPanel to receive view model; remove old orchestration
- [ ] 3.4 Verify existing component tests pass with new hook wiring
- [ ] 5.1 Update `view/AGENTS.md` with new frontend architecture folder conventions
