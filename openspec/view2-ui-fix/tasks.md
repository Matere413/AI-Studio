# Tasks: view2 UI Fix

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~600 (340 new + 260 modified) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Primitives) → PR 2 (Studio Shell) → PR 3 (Panels & Mobile) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Design tokens + 5 primitives + `useMediaQuery` + `mockAssets` + unit tests | PR 1 | All new files; zero regression risk; base = `main` |
| 2 | `uiStore` tri-state + `GenerationStudio` grid + `TopAppBar` mount + drawer default-open | PR 2 | Depends on PR 1 primitives; base = PR 1 branch or `main` after merge |
| 3 | `ChatSidebar` re-arrange + `InputBar` circular send + `WorkspaceCanvas` surface + `GenerationControls` + mobile overlay | PR 3 | Depends on PR 2; base = PR 2 branch or `main` after merge |

## Phase 1: Primitives & Tokens (PR 1)

- [x] 1.1 Add additive tokens to `view2/src/styles/colors_and_type.css`: `--color-canvas-dot: #3a2e22`, `--radius-pill: 999px`, `.surface-canvas`, `.btn-icon-circle`, `.status-dot` utility classes.
- [x] 1.2 Create `view2/src/features/generation/hooks/useMediaQuery.ts` — SSR-safe `useMediaQuery(breakpointPx: number): boolean` using `matchMedia` + `useState`/`useEffect`.
- [x] 1.3 Create `view2/src/features/generation/hooks/useMediaQuery.test.ts` — test at 1023px (false) and 1024px (true); mock `window.matchMedia`.
- [x] 1.4 Create `view2/src/features/generation/data/mockAssets.ts` — export `SEED_ASSETS: ReadonlyArray<AssetItem>` with 3 seed items.
- [x] 1.5 Create `view2/src/features/generation/components/primitives/StatusDot.tsx` + `StatusDot.module.css` — amber/green/red dot driven by `status` prop.
- [x] 1.6 Create `view2/src/features/generation/components/primitives/StatusDot.test.tsx` — renders correct color class per status.
- [x] 1.7 Create `view2/src/features/generation/components/primitives/IconButton.tsx` + `IconButton.module.css` — 44×44 touch target, `aria-label`, `--radius-pill`, focus ring.
- [x] 1.8 Create `view2/src/features/generation/components/primitives/IconButton.test.tsx` — assert `aria-label`, computed size ≥44px, focus-visible outline.
- [x] 1.9 Create `view2/src/features/generation/components/primitives/AgentAvatar.tsx` + `AgentAvatar.module.css` — 32×32 circle with initials fallback.
- [x] 1.10 Create `view2/src/features/generation/components/primitives/FileThumb.tsx` + `FileThumb.module.css` — thumbnail, filename, accessible remove button.
- [x] 1.11 Create `view2/src/features/generation/components/primitives/FileThumb.test.tsx` — renders name, calls `onRemove` on click.
- [x] 1.12 Create `view2/src/features/generation/components/primitives/TopAppBar.tsx` + `TopAppBar.module.css` — tabs row, actions slot, `StatusDot` integration, hamburger below 1024px.
- [x] 1.13 Create `view2/src/features/generation/components/primitives/TopAppBar.test.tsx` — tabs render, hamburger visible <1024px, status dot mounts.

## Phase 2: Studio Shell (PR 2)

- [x] 2.1 Modify `view2/src/features/generation/stores/uiStore.ts` — change `assetsDrawerOpen` to `"auto" | boolean`, add `aspectRatio: "1:1" | "16:9" | "9:16"`, add `setAssetsDrawer(v)` and `setAspectRatio(v)`. Default: `"auto"` + `"1:1"`.
- [x] 2.2 Update `view2/src/features/generation/stores/uiStore.test.ts` — test tri-state transitions, `toggleAssetsDrawer` flips from `"auto"` to explicit boolean, `aspectRatio` default and setter.
- [x] 2.3 Modify `view2/src/features/generation/components/GenerationStudio.module.css` — CSS Grid `320px 1fr 320px` with `var(--topbar-height) 1fr` rows; single-column collapse `@media (max-width: 1023px)`.
- [x] 2.4 Modify `view2/src/features/generation/components/GenerationStudio.tsx` — mount `<TopAppBar>` in top grid row; seed `SEED_ASSETS` via `useState` initializer; resolve drawer effective open from `"auto"` + `useMediaQuery(1024)`.
- [x] 2.5 Modify `view2/src/features/generation/components/AssetsDrawer.tsx` — accept effective `isOpen` prop; render as fixed overlay when viewport <1024px with `Esc`-to-close; add "Context Assets" label.
- [x] 2.6 Modify `view2/src/features/generation/components/AssetsDrawer.module.css` — add `@media (max-width: 1023px)` overlay styles (fixed position, backdrop, z-index).
- [x] 2.7 Update `view2/src/features/generation/components/AssetsDrawer.test.tsx` — mock `matchMedia`; test overlay mode <1024px, inline mode ≥1024px, `Esc` closes overlay.
- [x] 2.8 Update `view2/src/features/generation/components/GenerationStudio.test.tsx` — assert `TopAppBar` renders; assert drawer defaults open at ≥1024px.
- [x] 2.9 Update `view2/src/features/generation/components/GenerationStudio.responsive.test.ts` — change drawer breakpoint from `1279px` to `1023px`; keep `1279px` for chat narrowing.
- [x] 2.10 Update `view2/src/features/generation/components/GenerationStudio.integration.test.tsx` — verify submit + WS lifecycle shows green `StatusDot`; verify drawer toggle on mobile viewport.

## Phase 3: Panels & Mobile (PR 3)

- [x] 3.1 Create `view2/src/features/generation/components/GenerationControls.tsx` + `GenerationControls.module.css` — Speed (Fast/Quality) toggle + Aspect ratio (1:1/16:9/9:16) select; reads/writes `uiStore.aspectRatio`.
- [x] 3.2 Create `view2/src/features/generation/components/GenerationControls.test.tsx` — speed toggle dispatches; aspect select updates store; disabled state when no workflow.
- [x] 3.3 Modify `view2/src/features/generation/components/ChatSidebar.tsx` — add `<AgentAvatar>` above history; move speed/aspect out; mount `<GenerationControls>` below `<InputBar>`.
- [x] 3.4 Modify `view2/src/features/generation/components/ChatSidebar.module.css` — adjust flex order for new layout; ensure chat narrows at `1279px`.
- [x] 3.5 Update `view2/src/features/generation/components/ChatSidebar.test.tsx` — assert `AgentAvatar` renders; assert `GenerationControls` mounts below input; update `/send prompt/i` → `/send/i`.
- [x] 3.6 Modify `view2/src/features/generation/components/InputBar.tsx` — replace send button with `<IconButton>` wrapping `lucide-react` `Send`, `aria-label="Send prompt"`, disabled when empty/whitespace.
- [x] 3.7 Modify `view2/src/features/generation/components/InputBar.module.css` — circular send button styles (44×44, `--radius-pill`); add `Paperclip` icon button.
- [x] 3.8 Update `view2/src/features/generation/components/InputBar.test.tsx` — assert circular send disabled on empty; assert `aria-label="Send prompt"`; update test selectors.
- [x] 3.9 Modify `view2/src/features/generation/components/WorkspaceCanvas.tsx` — apply `.surface-canvas` class; add caption + progress bar chrome; render result image on `completed`.
- [x] 3.10 Modify `view2/src/features/generation/components/WorkspaceCanvas.module.css` — dotted background via `.surface-canvas`; artboard caption/progress styles.
- [x] 3.11 Update `view2/src/features/generation/components/WorkspaceCanvas.test.tsx` — assert `.surface-canvas` class present; assert progress caption updates; assert image renders on `completed`.
