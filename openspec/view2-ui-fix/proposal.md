# Proposal: view2 UI Fix

## Intent

Align `view2` with `expectativa.png` while preserving generation flow, WebSocket behavior, validation, and store contracts. The bottom-right “N” is the Next.js DevTools widget; ignore it completely.

## Scope

### In Scope
- Target-style `TopAppBar`: desktop tabs/actions/status; mobile hamburger.
- Existing CSS modules/tokens only; no Tailwind migration or UI library.
- `TopAppBar`, `FileThumb`, `StatusDot`, icon buttons, circular send.
- Move Speed/Aspect controls below chat input.
- Assets open by default on desktop, hidden on mobile, explicit toggle always available.

### Out of Scope
- Backend/API/WebSocket changes.
- Any DevTools “N” handling.
- Pixel-perfect token replacement or new UI library adoption.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `generative-ai-studio-frontend`: update layout, responsive navigation, assets drawer visibility/toggle behavior, and visual component requirements.

## Approach

Use exploration Option A: bridge the current token system. Keep `colors_and_type.css` as source of truth; add only `--color-canvas-dot`, `--radius-pill`, and small utilities. Build dotted chat/canvas surfaces with CSS gradients, target-like artboard chrome, amber `StatusDot`, `FileThumb` rows, and labeled icon buttons. Preserve Zustand/generation hooks; adapt only UI state for responsive Assets toggle behavior.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `GenerationStudio.tsx` | Modified | Top app bar, responsive layout, assets state. |
| `ChatSidebar.tsx`, `InputBar.tsx` | Modified | Avatar/meta, attachment, circular send, Speed/Aspect row. |
| `WorkspaceCanvas.tsx` | Modified | Dotted canvas, artboard caption/progress, file meta/status. |
| `AssetsDrawer.tsx` | Modified | Context Assets copy, file rows, upload CTA, visibility. |
| `components/primitives/*` | New | `TopAppBar`, `FileThumb`, `StatusDot`, icon helpers. |
| `colors_and_type.css`, `globals.css` | Modified | Additive tokens/utilities. |
| `components/*.test.tsx` | Modified | UI, accessibility, responsive assertions. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Responsive drawer regresses mobile usability | Med | Mobile-first tests for hidden-by-default drawer plus explicit toggle. |
| Icon-only controls lose accessibility | Med | Require `aria-label`, focus rings, 44px targets. |
| Visual changes break existing tests | High | Update assertions around preserved behavior, not obsolete labels. |

## Rollback Plan

Revert the UI component/CSS/test changes. No API, store contract, backend, or migration rollback is required.

## Dependencies

- Existing `lucide-react` icons.
- `expectativa.png` as visual reference.

## Success Criteria

- [ ] Desktop visually matches `expectativa.png` structure: top tabs/actions, open Assets, dotted canvas, polished chat input.
- [ ] Mobile hides Assets by default, exposes toggle, and collapses top tabs into hamburger.
- [ ] Next.js DevTools “N” remains ignored.
- [ ] Existing generation behavior and tests remain green after UI assertion updates.
