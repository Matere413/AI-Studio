# Design: view2 UI Fix

## Technical Approach

Bridge the existing `view2/` design system (CSS modules + `colors_and_type.css` tokens) with `expectativa.png` by adding presentation-only primitives, moving Speed/Aspect below the chat input, and switching the assets drawer to a viewport-aware default. Zero changes to backend, WebSocket, `useGenerationFlow`, or `generationStore`. `uiStore` gains a tri-state value; `aspect_ratio` is client-state only (backend out of scope per spec).

## Architecture Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Drawer visibility | `uiStore.assetsDrawerOpen: "auto" \| boolean` (default `"auto"`) | `"auto"` resolves to viewport default until the user explicitly toggles. |
| 2 | Viewport detection | New `useMediaQuery(1024)` hook (matchMedia + SSR-safe) | Matches spec `>=1024px` boundary; Zustand reads `window.innerWidth` synchronously, no flicker. |
| 3 | Studio layout | CSS Grid `320px 1fr 320px` / `var(--topbar-height) 1fr`; collapses to single column `<1024px` | 3-col desktop / 1-col mobile + topbar row becomes a one-rule change. |
| 4 | `TopAppBar` placement | Own grid row above the three columns | Keeps WS-driven `status` accessible while canvas scrolls; matches target. |
| 5 | Controls re-arrangement | `WorkflowSelector` stays in `ChatSidebar.controls`; new `GenerationControls` (Speed + Aspect) below `InputBar` | Spec moves speed/aspect only; aspect ratio is client-only state, not yet submitted. |
| 6 | Send button | `IconButton` primitive (44×44, `--radius-pill`) wrapping `lucide-react` `Send`, `aria-label="Send prompt"` | Spec mandates circular send; meets ≥44px touch target. |
| 7 | Dotted canvas | `.surface-canvas { background-image: radial-gradient(var(--color-canvas-dot) 1px, transparent 1px); background-size: 16px 16px; }` | Pure CSS, scales to DPR, no assets. |
| 8 | Mock assets | New `data/mockAssets.ts` constant (3 seed `AssetItem`s); `GenerationStudio` seeds `useState` on first mount | Co-located; clearing gallery does not regress the seed. |
| 9 | Token contract | **Additive only**: `--color-canvas-dot: #3a2e22`, `--radius-pill: 999px`, `.surface-canvas`, `.btn-icon-circle`, `.status-dot` | Spec and proposal forbid breaking existing tokens. |

## Data Flow

**Submit + WS lifecycle**:
```
User → InputBar → ChatSidebar.onSubmit → GenerationStudio.handleSubmit
   → useGenerationFlow.generate() → useGenerationStore
   → TopAppBar (StatusDot) + WorkspaceCanvas (caption + progress + image)
```

**Drawer visibility**:
```
useUiStore.assetsDrawerOpen ──┐
                              ├─▶  effective = "auto" ? useMediaQuery(1024) : value
useMediaQuery(1024) ──────────┘
                              ▼
                     AssetsDrawer (inline ≥1024px | fixed overlay <1024px)
```

`toggleAssetsDrawer` flips `"auto"` → opposite of current viewport default; explicit boolean toggles in place.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `view2/src/styles/colors_and_type.css` | Modify | Add `--color-canvas-dot`, `--radius-pill`, `.surface-canvas`, `.btn-icon-circle`, `.status-dot`. |
| `view2/src/features/generation/stores/uiStore.ts` | Modify | `assetsDrawerOpen: "auto" \| boolean`; `aspectRatio: "1:1" \| "16:9" \| "9:16"`; init `"auto"` + `"1:1"`. |
| `view2/src/features/generation/hooks/useMediaQuery.ts` | Create | SSR-safe `useMediaQuery(breakpointPx): boolean`. |
| `view2/src/features/generation/data/mockAssets.ts` | Create | 3 seed `AssetItem`s. |
| `view2/src/features/generation/components/primitives/{TopAppBar,FileThumb,StatusDot,IconButton,AgentAvatar}.tsx` (+css) | Create | 5 primitives, each with colocated CSS module. |
| `view2/src/features/generation/components/GenerationControls.tsx` (+css) | Create | Speed (F/Q) + Aspect (1:1/16:9/9:16) selects. |
| `view2/src/features/generation/components/{GenerationStudio,ChatSidebar,InputBar,WorkspaceCanvas,AssetsDrawer}.tsx` (+css) | Modify | Grid root + `TopAppBar` mount in studio; `AgentAvatar` + `GenerationControls` re-arrange in sidebar; `Paperclip` + circular `Send` in input; `.surface-canvas` + caption/progress chrome in canvas; default-open + `FileThumb` rows + `1023px` overlay breakpoint in drawer. |
| `view2/src/features/generation/components/*.test.tsx` (7 files) | Modify | `/send prompt/i` → `/send/i`; `awaiting generation` → status label; `1279px` → `1023px` for drawer rule; mock `matchMedia` for mobile tests. |

## Interfaces / Contracts

```ts
type DrawerState = "auto" | boolean;
type AspectRatio = "1:1" | "16:9" | "9:16";
interface UiStoreState {
  assetsDrawerOpen: DrawerState;        // default "auto"
  aspectRatio: AspectRatio;             // default "1:1" (client-only)
  toggleAssetsDrawer(): void;
  setAssetsDrawer(v: DrawerState): void;
  setAspectRatio(v: AspectRatio): void;
}
export function useMediaQuery(breakpointPx: number): boolean;
export const SEED_ASSETS: ReadonlyArray<AssetItem>;
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit | Tri-state `uiStore`, `useMediaQuery` at 1023/1024, `TopAppBar` tabs/status, `FileThumb` remove, `IconButton` aria-label+44px, `InputBar` circular send disabled, `AssetsDrawer` mobile overlay | Colocated `*.test.tsx`; mock `matchMedia` for viewport. |
| Integration | `GenerationStudio`: submit + WS lifecycle green; toggle drawer on mobile; upload adds new `FileThumb`; reference validation still blocks `identidad_gguf` | `GenerationStudio.integration.test.tsx`. |
| CSS string | `@media (max-width: 1023px)` for drawer; keep `1279px` for chat narrowing | Update `GenerationStudio.responsive.test.ts`. |
| Manual | Desktop parity vs `expectativa.png`; mobile shows hamburger + hidden drawer | Screenshot in dev. |

## Migration / Rollout

No data migration. **PR size risk**: estimated diff ~600 lines (340 new + 260 modified) exceeds the 400-line review budget. Recommend **chained PRs**: (1) tokens + primitives + tests, (2) `GenerationStudio` grid + `TopAppBar` + drawer default, (3) `ChatSidebar`/`InputBar`/`WorkspaceCanvas` + `GenerationControls` + mobile breakpoint. Revert = `git revert` per slice.

## Open Questions

- `aspect_ratio` is not submitted to backend. Confirm with PM: disabled or inert?
- Mobile overlay: spec silent on `Esc`-to-close + focus trap. Proposed: `Esc` closes, no full focus trap.
- Chat narrowing stays at `1279px`; spec only mandates `<1024px` for drawer. Intentional dual breakpoints.
