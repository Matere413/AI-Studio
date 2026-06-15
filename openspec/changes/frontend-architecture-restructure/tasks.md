# Tasks: Frontend Architecture Restructure

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1800 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (moves) → PR 2 (hook extraction + docs) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Move-only restructure | PR 1 | File relocation, import updates, shared move, cleanup. All tests pass. |
| 2 | Hook extraction + docs | PR 2 | Extract useGenerationFlow, refactor PromptPanel, update AGENTS.md. |

## Phase 1: Foundation / Worktree Setup

- [x] 1.1 Create git worktree at separate path for implementation isolation
- [x] 1.2 Create dirs: `features/generation/{api,components,hooks,stores}`, `shared/components/ui/`
- [x] 1.3 Create `features/generation/api/types.ts` — GenerationParameters, JobEvent, WS event types
- [x] 1.4 Move `PixelProgressBar.tsx` + CSS + test → `shared/components/ui/`
- [x] 1.5 Centralize `next/image` mock in `src/test/setup.ts`

## Phase 2: Core File Moves

- [x] 2.1 Move `api.ts` → `features/generation/api/client.ts`; update WS/HTTP exports
- [x] 2.2 Move `api.test.ts` + `api-ws.test.ts` → `features/generation/api/`
- [x] 2.3 Move `generationStore.ts` + test → `features/generation/stores/`
- [x] 2.4 Rename/move components: StudioLayout→GenerationStudio, Sidebar→PromptPanel, Canvas→OutputCanvas, ImageGallery→SessionHistory, TerminalLog→EventTerminal
- [x] 2.5 Move/rename co-located CSS modules and tests for renamed components
- [x] 2.6 Update `page.tsx` import to `features/generation/components/GenerationStudio`
- [x] 2.7 Delete unused `page.module.css` and duplicate `ImageGallery.test.ts`

## Phase 3: Hook Extraction

- [x] 3.1 [RED] Write failing tests for `useGenerationFlow` (submit, cancel, reset, WS lifecycle, retry exhaustion)
- [x] 3.2 [GREEN] Extract `useGenerationFlow` in `features/generation/hooks/` — HTTP submit, WS connect/retry/cleanup from Sidebar
- [x] 3.3 [REFACTOR] Convert Sidebar→PromptPanel to receive view model; remove old orchestration
- [x] 3.4 Verify existing component tests pass with new hook wiring

## Phase 4: Verification

- [x] 4.1 Run `npm exec vitest -- --run`; fix all import/mock issues
- [x] 4.2 Verify behavior preservation per spec: generation submit, WS lifecycle, state transitions, preview, validation, gallery

## Phase 5: Cleanup / Documentation

- [x] 5.1 Update `view/AGENTS.md` with new frontend architecture folder conventions
