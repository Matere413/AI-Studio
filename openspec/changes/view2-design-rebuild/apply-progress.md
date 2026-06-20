# Apply Progress: view2-design-rebuild — PR 1 + PR 2 + PR 3 + PR 4 + PR 5 (Scaffold + Tokens + Smoke Test + State/API + Shell/Controls + Output/History + Accessibility/Polish)

## PR 1 / Phase 1: Scaffold, Tokens & Smoke Test

### Slice Boundary
- Start: empty `view2/` workspace.
- End: Next.js scaffold, copied design tokens, canvas CSS, placeholder `GenerationStudio`, smoke test, and successful build verification.
- Out of scope: generation state, API client, WebSocket lifecycle, real chat/canvas/assets UI, accessibility polish.

### Completed Tasks
- [x] 1.1 `view2/package.json`
- [x] 1.2 `view2/next.config.ts`
- [x] 1.3 `view2/tsconfig.json`
- [x] 1.4 `view2/vitest.config.ts`
- [x] 1.5 `view2/src/test/setup.ts`
- [x] 1.6 `view2/src/styles/colors_and_type.css`
- [x] 1.7 `view2/src/styles/canvas.css`
- [x] 1.8 `view2/src/app/globals.css`
- [x] 1.9 `view2/src/app/layout.tsx`
- [x] 1.10 `view2/src/app/page.tsx`
- [x] 1.11 Smoke test for the `/view2/` entry page
- [x] 1.12 Vitest and Next build verification

### TDD Evidence
| Step | Command | Result |
|------|---------|--------|
| RED | `npx vitest run src/app/page.test.tsx` | Failed as expected: `Failed to resolve import "./page"` |
| GREEN | `npx vitest run src/app/page.test.tsx` | Passed after scaffold and placeholder implementation |
| VERIFY | `npx vitest run` | Passed 1/1 |
| VERIFY | `npx next build` | Succeeded, static route generated |
| POST-REVIEW VERIFY | `npm test` | Passed 1/1 after CSS readability cleanup |
| POST-REVIEW VERIFY | `npm run build` | Passed after CSS readability cleanup |
| POST-REVIEW VERIFY | `npm run typecheck` | Skipped: no `typecheck` script exists in `view2/package.json` |

### Commands Run
- `npm install`
- `npx vitest run src/app/page.test.tsx`
- `npx vitest run`
- `npx next build`
- `npm test`
- `npm run build`

### Files Changed
- `view2/package.json`
- `view2/package-lock.json`
- `view2/next.config.ts`
- `view2/tsconfig.json`
- `view2/vitest.config.ts`
- `view2/next-env.d.ts`
- `view2/.gitignore`
- `view2/src/test/setup.ts`
- `view2/src/styles/colors_and_type.css`
- `view2/src/styles/canvas.css`
- `view2/src/app/globals.css`
- `view2/src/app/layout.tsx`
- `view2/src/app/page.tsx`
- `view2/src/app/page.test.tsx`
- `view2/src/features/generation/components/GenerationStudio.tsx`

### Known Risks / Follow-ups
- The design-system CSS expects `/fonts/*` assets that are not yet mirrored under `view2/public/`.
- PR 1 is still a scaffold slice; real state, API, WebSocket, and panel work remain for later PRs.
- The copied token file is large, so subsequent slices must stay tightly scoped to respect review load.
- Post-apply readability review found duplicated grid width values in `canvas.css`; fixed by naming the shell column widths as local CSS custom properties and removing unused future-facing topbar CSS.
- Final readability review left a non-blocking suggestion: copied canonical `colors_and_type.css` includes unused utility classes such as `.crt`, `.grain`, `.cursor`, and `.pixelated`. They remain because PR 1 copied the design-system CSS as planned; do not use retro utilities in `view2` components.

### Next Slice Recommendation
- Superseded by completed PR 2 below: generation types, stores, API client, WebSocket lifecycle, hook, and image resize helper with unit tests.

## PR 2 / Phase 2: State, API, WebSocket, Hook & Image Helper (TDD)

### Slice Boundary
- Start: PR 1 scaffold complete, with only shell/token files in `view2/`.
- End: backend-aligned types, Zustand stores, API client, WebSocket lifecycle, generation hook, image resize helper, plus green unit/verification runs.
- Out of scope: studio shell, chat/sidebar, canvas/artboard UI, assets drawer UI, accessibility polish.

### Completed Tasks
- [x] 2.1 RED: write `api/types.test.ts` asserting `WorkflowName` union and `JobEvent` discriminant exhaustiveness
- [x] 2.2 GREEN: create `api/types.ts` with `WorkflowName`, `JobEventName`, `JobEvent` union, `GenerationState`, `GenerationParameters`
- [x] 2.3 RED: write `stores/generationStore.test.ts` covering `addEvent` state transitions (`booting_server→booting`, `completed→done`, `error→error`), prompt/parameter setters, workflow_name binding
- [x] 2.4 GREEN: create `stores/generationStore.ts` porting fields, validators, `addEvent` reducer
- [x] 2.5 RED: write `stores/uiStore.test.ts` covering tri-state drawer, `setMobile()`, Esc-close
- [x] 2.6 GREEN: create `stores/uiStore.ts`
- [x] 2.7 RED: write `api/client.test.ts` asserting payload shape per workflow (no `aspect_ratio`), `submitGenerate` body, retry cap (3), exponential backoff (1s/2s/4s)
- [x] 2.8 GREEN: create `api/client.ts` with `submitGenerate`, `getWsUrl`, `getImageUrl`, `connectWebSocket`
- [x] 2.9 RED: write `hooks/useGenerationFlow.test.tsx` covering submit, cancel, exhausted-retry
- [x] 2.10 GREEN: create `hooks/useGenerationFlow.ts`
- [x] 2.11 RED: write `utils/imageResize.test.ts` covering PNG/JPEG validation, ≤5MB accept, 5–10MB compress, >10MB reject
- [x] 2.12 GREEN: create `utils/imageResize.ts`
- [x] 2.13 Verify: `npx vitest run` all green, `npx tsc --noEmit` clean

### TDD Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `view2/src/features/generation/api/types.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 2.2 | `view2/src/features/generation/api/types.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 2.3 | `view2/src/features/generation/stores/generationStore.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 3 cases | ✅ Clean |
| 2.4 | `view2/src/features/generation/stores/generationStore.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 3 behaviors | ✅ Clean |
| 2.5 | `view2/src/features/generation/stores/uiStore.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 2.6 | `view2/src/features/generation/stores/uiStore.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 3 drawer states | ✅ Clean |
| 2.7 | `view2/src/features/generation/api/client.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 cases | ✅ Clean |
| 2.8 | `view2/src/features/generation/api/client.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 behaviors | ✅ Clean |
| 2.9 | `view2/src/features/generation/hooks/useGenerationFlow.test.tsx` | Integration-style unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 cases | ✅ Clean |
| 2.10 | `view2/src/features/generation/hooks/useGenerationFlow.test.tsx` | Integration-style unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 behaviors | ✅ Clean |
| 2.11 | `view2/src/features/generation/utils/imageResize.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 cases | ✅ Clean |
| 2.12 | `view2/src/features/generation/utils/imageResize.test.ts` | Unit | N/A (new) | ✅ Written | ✅ Passed | ✅ 4 behaviors | ✅ Clean |
| 2.13 | `npx vitest run` + `npx tsc --noEmit` | Verify | ✅ 7/7 files, 20/20 tests | ✅ Red import failures on missing modules | ✅ Full suite passed | ✅ N/A | ✅ Clean |

### Commands Run
- `npx vitest run src/features/generation/api/types.test.ts src/features/generation/stores/generationStore.test.ts src/features/generation/stores/uiStore.test.ts src/features/generation/api/client.test.ts src/features/generation/hooks/useGenerationFlow.test.tsx src/features/generation/utils/imageResize.test.ts`
- `npx vitest run`
- `npx tsc --noEmit`
- `npm test`
- `npm run build`

### Post-Review Fixes
- Vitest now forbids focused tests in normal runs via `allowOnly: false`.
- Image resize now uses a 5MB soft resize threshold and a 10MB hard acceptance limit, with tests covering compressed output in the 5–10MB range.
- WebSocket retry exhaustion now survives open/abnormal-close cycles, and the retry defaults are exported from the API client as a single source of truth.
- The Esc-close store test now exercises `handleEscapeKey()` directly.
- Prompt length validation now uses a named constant instead of an inline magic number.
- The studio shell now drives `uiStore.setMobile()` from viewport state, collapses the assets drawer below 1280px, and exposes the responsive column widths through shell CSS variables for testable layout assertions.
- Removed reference assets now leave `referenceGallery` through a store action, preventing hydration from restoring deleted uploads.
- `WorkflowSelector` now reuses `WORKFLOW_NAMES` from the API types source.
- The tasks list no longer claims a focus trap implementation that is not present in PR 3.
- The apply-progress title now reflects the cumulative PR 1 + PR 2 scope.

### Files Changed
- `view2/src/features/generation/api/types.test.ts`
- `view2/src/features/generation/api/types.ts`
- `view2/src/features/generation/api/client.test.ts`
- `view2/src/features/generation/api/client.ts`
- `view2/src/features/generation/stores/generationStore.test.ts`
- `view2/src/features/generation/stores/generationStore.ts`
- `view2/src/features/generation/stores/uiStore.test.ts`
- `view2/src/features/generation/stores/uiStore.ts`
- `view2/src/features/generation/hooks/useGenerationFlow.test.tsx`
- `view2/src/features/generation/hooks/useGenerationFlow.ts`
- `view2/src/features/generation/utils/imageResize.test.ts`
- `view2/src/features/generation/utils/imageResize.ts`

### Known Risks / Follow-ups
- `useGenerationFlow` currently keeps the payload assembly logic local to the hook; when the UI slice lands, this must stay synchronized with prompt/reference controls.
- `uiStore` now encodes the drawer tri-state, but the actual responsive shell in PR 3 still needs to wire those transitions to viewport changes and Esc handling.
- The image helper returns the original file for inputs at or below 5MB, which is correct for this slice but must remain aligned with the upload UI.

### Next Slice Recommendation
- PR 3: studio shell, chat sidebar, workflow selector, speed selector, assets drawer, and responsive grid.

## PR 3 / Phase 3: Studio Shell & Controls (Strict TDD)

### Slice Boundary
- Start: PR 2 completed, with only the state/API layer available and the shell still placeholder-only.
- End: 3-pane studio shell, chat sidebar, workflow selector, speed selector, assets drawer, responsive grid behavior, shared UI primitives, and slice verification.
- Out of scope: OutputCanvas, StatusDot, EventTerminal, SessionHistory, topbar controls, accessibility polish.

### Completed Tasks
- [x] 3.1 `GenerationStudio.test.tsx` three-pane regions and responsive shell
- [x] 3.2 `GenerationStudio.tsx` + `GenerationStudio.module.css` three-column shell
- [x] 3.3 `ChatSidebar.test.tsx` agent avatar, message list, prompt input
- [x] 3.4 `ChatSidebar.tsx` agent header, history list, `<InputBar />`
- [x] 3.5 `WorkflowSelector.test.tsx` workflow options, default, store binding
- [x] 3.6 `WorkflowSelector.tsx` + `SpeedSelector.tsx` pill-row listboxes
- [x] 3.7 `InputBar.test.tsx` Enter submit and empty disabled state
- [x] 3.8 `InputBar.tsx` prompt composer with workflow/speed rail
- [x] 3.9 `AssetsDrawer.test.tsx` upload, thumbnail, filename, remove, modal behavior
- [x] 3.10 `AssetsDrawer.tsx` file upload drawer with Esc-close and `aria-modal`
- [x] 3.11 Shared UI primitives: `IconButton.tsx`, `AgentAvatar.tsx`, `FileThumb.tsx`, `Pill.tsx`
- [x] 3.12 `shared/hooks/useMediaQuery.ts` SSR-safe desktop breakpoint hook
- [x] 3.13 Responsive shell test for collapse below 1280px
- [x] 3.14 `useMediaQuery` wired into `GenerationStudio`; mobile drawer overlay
- [x] 3.15 Verification: `npx vitest run`, `npx next build`

### TDD Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1-3.2 | `view2/src/features/generation/components/GenerationStudio.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Desktop + mobile cases | ✅ Clean |
| 3.3-3.4 | `view2/src/features/generation/components/ChatSidebar.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Empty + seeded history | ✅ Clean |
| 3.5-3.6 | `view2/src/features/generation/components/WorkflowSelector.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Default + binding | ✅ Clean |
| 3.7-3.8 | `view2/src/features/generation/components/InputBar.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Submit + disabled | ✅ Clean |
| 3.9-3.10 | `view2/src/features/generation/components/AssetsDrawer.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Upload/remove + mobile dialog + gallery cleanup | ✅ Clean |
| 3.11 | `view2/src/shared/components/ui/{IconButton,AgentAvatar,FileThumb,Pill}.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Covered through consumer tests | ✅ Clean |
| 3.12 | `view2/src/shared/hooks/useMediaQuery.ts` | Hook | N/A (new) | ✅ Written | ✅ Passed | ✅ Desktop/mobile breakpoint cases | ✅ Clean |
| 3.13-3.14 | `view2/src/features/generation/components/GenerationStudio.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ Responsive grid collapse verified | ✅ Clean |
| 3.15 | `npx vitest run`, `npx next build` | Verify | ✅ All component suites green | ✅ Written | ✅ Passed | ✅ Full suite + production build | ✅ Clean |

### Commands Run
- `npx vitest run src/features/generation/components/GenerationStudio.test.tsx src/features/generation/components/ChatSidebar.test.tsx src/features/generation/components/WorkflowSelector.test.tsx src/features/generation/components/InputBar.test.tsx src/features/generation/components/AssetsDrawer.test.tsx`
- `npx vitest run`
- `npx next build`

### Post-Review Fixes
- Wired viewport changes into `uiStore.setMobile()` from `GenerationStudio` so the assets drawer auto-collapses below 1280px.
- Replaced the hard-coded shell grid widths with named responsive CSS variables, and added test assertions for the desktop and mobile column widths.
- Moved `AssetsDrawer` to the store-driven mobile state, added URL removal from `referenceGallery`, and kept the mobile dialog/escape behavior.
- Reused `WORKFLOW_NAMES` in `WorkflowSelector` instead of duplicating the workflow list.
- Seeded `useMediaQuery` from `matchMedia()` synchronously to keep the initial viewport state aligned with the browser.
- Corrected the tasks list so PR 3 no longer claims a focus trap implementation that does not exist.
- Removed the duplicated numeric 1280/1279 breakpoint from CSS; mobile panel behavior now follows `data-layout="mobile"`, with `layout.ts` remaining the breakpoint source of truth.

### Post-Review Verification
- `npm test` ✅
- `npx tsc --noEmit` ✅
- `npm run build` ✅
- Final breakpoint cleanup verification: `npm test` ✅ 12 files / 33 tests, `npx tsc --noEmit` ✅, `npm run build` ✅

### Files Changed
- `view2/src/features/generation/components/GenerationStudio.tsx`
- `view2/src/features/generation/components/GenerationStudio.module.css`
- `view2/src/features/generation/layout.ts`
- `view2/src/features/generation/stores/generationStore.ts`
- `view2/src/features/generation/components/ChatSidebar.tsx`
- `view2/src/features/generation/components/InputBar.tsx`
- `view2/src/features/generation/components/WorkflowSelector.tsx`
- `view2/src/features/generation/components/SpeedSelector.tsx`
- `view2/src/features/generation/components/AssetsDrawer.tsx`
- `view2/src/features/generation/components/*.test.tsx`
- `view2/src/shared/components/ui/IconButton.tsx`
- `view2/src/shared/components/ui/AgentAvatar.tsx`
- `view2/src/shared/components/ui/FileThumb.tsx`
- `view2/src/shared/components/ui/Pill.tsx`
- `view2/src/shared/hooks/useMediaQuery.ts`

### Known Risks / Follow-ups
- The assets drawer keeps local file-name metadata in component state, while the store still persists only URLs.
- `SpeedSelector` remains a generic speed toggle and does not yet branch on workflow-specific capability differences.
- Output canvas, generation status, event terminal, and history still belong to PR 4.

### Next Slice Recommendation
- PR 4: OutputCanvas, StatusDot, EventTerminal, SessionHistory, artboard chrome, and integration flow test.

## PR 4 / Phase 4: Output, Status & History (Strict TDD)

### Slice Boundary
- Start: PR 3 completed, with the 3-pane shell, controls, and responsive layout already in place.
- End: center-column top bar, dotted output canvas, status dot, event terminal, session history, and a working prompt→WS→done→history integration test.
- Out of scope: accessibility/focus polish, reduced-motion, keyboard-audit fixes, and any backend/API contract changes.

### Completed Tasks
- [x] 4.1 `OutputCanvas.test.tsx` dotted canvas, artboard chrome, prompt caption, bottom rail, completed image
- [x] 4.2 `OutputCanvas.tsx` dotted artboard surface and `<Image>` result rendering
- [x] 4.3 `StatusDot.test.tsx` pulse, state color, `aria-live="polite"`
- [x] 4.4 `StatusDot.tsx`
- [x] 4.5 `EventTerminal.test.tsx` scrollable log and monospace status
- [x] 4.6 `EventTerminal.tsx`
- [x] 4.7 `SessionHistory.test.tsx` newest-first thumbnails on completion
- [x] 4.8 `SessionHistory.tsx`
- [x] 4.9 `TopAppBar.tsx` disabled Export/Publish/Search/Fullscreen controls
- [x] 4.10 integration test: prompt → submit → mock WS events → done → history item
- [x] 4.11 `GenerationStudio.tsx` wired to the new center-column components
- [x] 4.12 Verify: `npm test`, `npm run build`

### TDD Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1-4.2 | `view2/src/features/generation/components/OutputCanvas.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 4.3-4.4 | `view2/src/features/generation/components/StatusDot.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 4.5-4.6 | `view2/src/features/generation/components/EventTerminal.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 4.7-4.8 | `view2/src/features/generation/components/SessionHistory.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 4.9 | `view2/src/features/generation/components/TopAppBar.test.tsx` | Component | N/A (new) | ✅ Written | ✅ Passed | ✅ 2 cases | ✅ Clean |
| 4.10-4.11 | `view2/src/features/generation/components/GenerationStudio.test.tsx` | Integration | ✅ 2/2 shell tests passing | ✅ Written | ✅ Passed | ✅ Prompt→WS→history flow | ✅ Clean |
| 4.12 | `npm test`, `npm run build` | Verify | ✅ Full suite green before build | ✅ N/A | ✅ Passed | ✅ Full suite + production build | ✅ Clean |

### Commands Run
- `npm test -- src/features/generation/components/OutputCanvas.test.tsx src/features/generation/components/StatusDot.test.tsx src/features/generation/components/EventTerminal.test.tsx src/features/generation/components/SessionHistory.test.tsx src/features/generation/components/TopAppBar.test.tsx src/features/generation/components/GenerationStudio.test.tsx`
- `npm test`
- `npm run build`

### Post-Review Fixes
- Treated `JobEvent.progress` as an integer percentage throughout PR 4 and updated the status/event tests to use backend-aligned values.
- Added the canonical session history contract: thumbnail, 80-character prompt truncation, and visible timestamp.
- Preserved terminal completed/error visibility by keeping the final terminal event in store state after `currentJob` clears.
- Removed unused workspace CSS and moved duplicated inline canvas/log styling into CSS module rules.
- Moved the artboard border to CSS and updated the canvas test to assert classes/semantics instead of a raw color literal.

### Post-Review Verification
- `npm test` ✅
- `npx tsc --noEmit` ✅
- `npm run build` ✅

### Files Changed
- `view2/src/features/generation/components/GenerationStudio.tsx`
- `view2/src/features/generation/components/GenerationStudio.module.css`
- `view2/src/features/generation/components/OutputCanvas.tsx`
- `view2/src/features/generation/components/OutputCanvas.test.tsx`
- `view2/src/features/generation/components/StatusDot.tsx`
- `view2/src/features/generation/components/StatusDot.test.tsx`
- `view2/src/features/generation/components/EventTerminal.tsx`
- `view2/src/features/generation/components/EventTerminal.test.tsx`
- `view2/src/features/generation/components/SessionHistory.tsx`
- `view2/src/features/generation/components/SessionHistory.test.tsx`
- `view2/src/features/generation/components/TopAppBar.tsx`
- `view2/src/features/generation/components/TopAppBar.test.tsx`
- `view2/src/features/generation/components/GenerationStudio.test.tsx`
- `openspec/changes/view2-design-rebuild/apply-progress.md`
- `openspec/changes/view2-design-rebuild/tasks.md`

### Known Risks / Follow-ups
- PR 5 still needs the accessibility audit, keyboard nav, reduced-motion override, and focus-restoration checks.
- The verified submit path is Enter-key based; pointer submission via the visible send button remains a later follow-up if required.
- The output/history flow is intentionally local-state only and still depends on the existing backend contract.

### Next Slice Recommendation
- PR 5: accessibility audit, keyboard navigation, reduced-motion, focus restoration, and snapshot/contrast checks.

## Runtime Hotfix: Font Requests + Hydration-Safe Studio Layout

### Scope
- Neutralize missing `/fonts/*` requests in the copied view2 design tokens.
- Keep the `GenerationStudio` shell on a deterministic SSR/default layout until mount, then apply the measured viewport layout.

### Completed Tasks
- [x] Removed custom `@font-face` imports from `view2/src/styles/colors_and_type.css` and switched view2 typography to system font stacks only.
- [x] Added a mount gate in `view2/src/features/generation/components/GenerationStudio.tsx` so `data-layout` and CSS variables stay server-safe during hydration.
- [x] Added regression coverage for the layout resolver and for missing font asset references.

### Verification
| Command | Result |
|---------|--------|
| `npm test` | Passed (18 files / 48 tests) |
| `npx tsc --noEmit` | Passed |
| `npm run build` | Passed |

### Files Changed
- `view2/src/styles/colors_and_type.css`
- `view2/src/styles/colors_and_type.test.ts`
- `view2/src/features/generation/components/GenerationStudio.tsx`
- `view2/src/features/generation/components/GenerationStudio.test.tsx`
- `openspec/changes/view2-design-rebuild/apply-progress.md`

### Known Risks / Follow-ups
- PR 5 still owns accessibility, keyboard navigation, reduced-motion, and focus-restoration work.
- The design token file remains the shared source for typography and color values, so future copy-pastes should keep font URLs out of `view2`.

## Hydration Test Correction: Deterministic Post-Hydration Desktop Render

### Scope
- Replace the earlier hydration smoke check with a real hydration regression test that proves the client mount path, not just the SSR markup.

### Completed Tasks
- [x] Rendered server HTML with `renderToString(<GenerationStudio />)`, hydrated it under a desktop `matchMedia()` environment, and flushed hydration/effects with React `act()`.
- [x] Spied on `console.error` and `console.warn` to assert no React hydration mismatch warning/error is emitted.
- [x] Asserted the final post-hydration desktop shell layout and responsive CSS variables after mount.

### Verification
| Command | Result |
|---------|--------|
| `npx vitest run src/features/generation/components/GenerationStudio.test.tsx` | Passed |
| `npm test` | Passed |
| `npx tsc --noEmit` | Passed |
| `npm run build` | Passed |

### Files Changed
- `view2/src/features/generation/components/GenerationStudio.test.tsx`
- `openspec/changes/view2-design-rebuild/apply-progress.md`

### Known Risks / Follow-ups
- None for this slice.

## PR 5 / Phase 5: Accessibility & Polish (Strict TDD)

### Slice Boundary
- Start: PR 4 complete, with the output/status/history shell already stable and hydration-safe.
- End: ARIA audit coverage, keyboard focus trap/restoration for the mobile assets drawer, focus-visible styling, reduced-motion override, contrast verification, and full suite/build proof.
- Out of scope: backend/API contract changes, new workflows, and any non-PR5 structural redesign.

### Completed Tasks
- [x] 5.1 Write ARIA audit test: all icon buttons have `aria-label`, drawers have `role="dialog"`, landmarks correct
- [x] 5.2 Write keyboard-nav test: cover the mobile assets drawer tab cycle and focus restoration
- [x] 5.3 Add `prefers-reduced-motion: reduce` override to `GenerationStudio.module.css` for the real shell/status selectors
- [x] 5.4 Verify focus trap restores focus to trigger on drawer close
- [x] 5.5 Visual test: focus-visible selector coverage and reduced-motion guard in component CSS
- [x] 5.6 Verify color contrast: `--fg-1` on `--bg-0` ≥ 12:1, `--fg-3` on `--bg-0` ≥ 4.5:1
- [x] 5.7 Final: `npx vitest run`, `npx tsc --noEmit`, `npx next build` all green

### TDD Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 5.1 | `view2/src/features/generation/components/GenerationStudio.test.tsx` | Component / integration | ✅ Existing studio suites green | ✅ Written | ✅ Passed | ✅ Landmark + label audit | ✅ Clean |
| 5.2-5.4 | `view2/src/features/generation/components/AssetsDrawer.test.tsx` | Component | ✅ Existing drawer tests green | ✅ Written | ✅ Passed | ✅ Tab cycle + focus restore | ✅ Clean |
| 5.3-5.5 | `view2/src/features/generation/components/GenerationStudio.visual.test.ts` | File-level visual verification | ✅ Existing CSS checks green | ✅ Written | ✅ Passed | ✅ Focus-visible selectors + reduced-motion guard | ✅ Clean |
| 5.6 | `view2/src/styles/colors_and_type.test.ts` | File-level token verification | ✅ Existing font-asset check green | ✅ Written | ✅ Passed | ✅ Contrast ratios validated for `--fg-1` / `--fg-3` on `--bg-0` | ✅ Clean |
| 5.7 | `npm test`, `npx tsc --noEmit`, `npx next build` | Verify | ✅ Full suite green | ✅ Written | ✅ Passed | ✅ Full suite + build + typecheck | ✅ Clean |

### Commands Run
- `npx vitest run src/shared/components/ui/IconButton.test.tsx src/features/generation/components/GenerationStudio.visual.test.ts src/features/generation/components/AssetsDrawer.test.tsx src/features/generation/components/GenerationStudio.test.tsx`
- `npm test`
- `npx tsc --noEmit`
- `npm run build`

### Post-Review Verification
- Focused regression tests: `npx vitest run src/shared/components/ui/IconButton.test.tsx src/features/generation/components/GenerationStudio.visual.test.ts src/features/generation/components/AssetsDrawer.test.tsx src/features/generation/components/GenerationStudio.test.tsx` ✅ 4/4 files, 12/12 tests
- Full test suite: `npm test` ✅ 20/20 files, 54/54 tests
- TypeScript check: `npx tsc --noEmit` ✅
- Production build: `npm run build` ✅

### Post-Review Fixes
- Moved reduced-motion suppression into `GenerationStudio.module.css` so it targets the real `.shell` and `.statusTone[data-pulsing="true"]` selectors.
- Updated the keyboard-nav and visual-polish docs to match the verified mobile drawer tab cycle, focus-visible selector coverage, and actual contrast tokens.
- Merged caller `className` with the shared `IconButton` class so the focus-visible styling cannot be overwritten.
- Simplified the mobile drawer focus loop by naming the focusable selector and replacing the nested ternary with a small branch.

### Files Changed
- `view2/src/features/generation/components/AssetsDrawer.tsx`
- `view2/src/features/generation/components/AssetsDrawer.test.tsx`
- `view2/src/features/generation/components/GenerationStudio.module.css`
- `view2/src/features/generation/components/GenerationStudio.test.tsx`
- `view2/src/features/generation/components/GenerationStudio.visual.test.ts`
- `view2/src/shared/components/ui/IconButton.tsx`
- `view2/src/shared/components/ui/IconButton.test.tsx`
- `view2/src/styles/canvas.css`
- `view2/src/styles/colors_and_type.test.ts`
- `openspec/changes/view2-design-rebuild/tasks.md`
- `openspec/changes/view2-design-rebuild/apply-progress.md`

### Known Risks / Follow-ups
- The focus-trap/restore pattern now lives in `AssetsDrawer`; any future modal drawer in `view2` should reuse the same accessibility contract.
- Reduced-motion suppression is now scoped to the real `GenerationStudio` shell and pulsing status tone selectors.

### Next Slice Recommendation
- `sdd-verify`
