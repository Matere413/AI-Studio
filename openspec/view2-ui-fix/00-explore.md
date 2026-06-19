# Exploration: view2 UI Fix

> Visual gap analysis between `expectativa.png` (target) and `realidad.png` (current).
> The current `view2/` implementation is the **shell** of the target experience — layout
> region, store wiring, and design tokens are all in place, but most of the **visual
> richness** and **content affordances** from the target are still missing.

---

## Current State

`view2/` is a Next.js 16 + React 19 App Router app that boots a single page
`/` rendering `<GenerationStudio />` (see `view2/src/app/page.tsx` →
`view2/src/features/generation/components/GenerationStudio.tsx`).

The studio is a three-pane flex layout:

```
ChatSidebar (320px, surface panel) │ workspacePane (flex)
                                  ├─ WorkspaceCanvas (flex 1)
                                  └─ AssetsDrawer (toggle rail + optional 280px drawer)
```

State is managed with two Zustand stores (`generationStore`, `uiStore`) and one
hook (`useGenerationFlow`) that wires HTTP `submitGenerate` + WebSocket events
to the store. The API client talks to the backend via the `next.config.ts`
rewrites (`/api/generate`, `/api/ws/generate/:jobId`, `/api/images/:jobId`).

Design tokens live in `view2/src/styles/colors_and_type.css` (CSS custom
properties) and are consumed via a few utility classes in `globals.css`
(`.btn`, `.btn-primary`, `.input`, `.surface-panel`, `.text-mono`, `.text-caps`)
plus per-component CSS modules. No Tailwind, no styled-components — plain CSS
modules + a small global token sheet.

Tests are colocated (`*.test.tsx`) using `vitest` + Testing Library. The
`view2/public/fonts/` directory exists but is empty — no custom fonts are
shipped, and the design system falls back to `system-ui` for both display
and body stacks.

---

## Visual Diff: Target vs Current

### 1. Top App Bar (center column)

| Aspect | Target (`expectativa.png`) | Current (`realidad.png`) |
| --- | --- | --- |
| Title | "I-Studio Workspace" | "I-Studio Workspace" (matches) |
| Tabs | "Studio Canvas" (active, orange underline) | none |
| Sidebar toggle | "Assets" (highlighted, with icon) | "Assets" sits in a separate column |
| Action buttons | "Export" (ghost), "Publish" (primary orange) | none |
| Status indicator | orange dot + "GENERATING…" | "AWAITING GENERATION" mono text + 2px progress bar |
| File meta | "output_9348.png (1024x1024) — GENERATING" + search + fullscreen icons | none |

**Files involved:** `WorkspaceCanvas.tsx` header section, `GenerationStudio.tsx`
layout shell, new `TopAppBar` would be needed.

### 2. Studio Canvas (center)

| Aspect | Target | Current |
| --- | --- | --- |
| Background | dotted grid pattern (small dots on dark surface) | flat `--color-bg-base` |
| Artboard | large square image with caption "[ Minimalist coffee cup on concrete ]" | empty square with "No output yet" |
| Caption / progress chrome | orange "GENERATING…" tag in top-right of artboard, thin orange bar under image | none |
| Tab affordance | the tab bar lives at the top | no tabs |

**Files involved:** `WorkspaceCanvas.module.css` `.canvas` and `.artboard`
classes; the dotted grid is not implemented anywhere.

### 3. Left Panel — Agent Chat

| Aspect | Target | Current |
| --- | --- | --- |
| Header | orange robot avatar + "Agent Chat" + gear icon | "Agent Chat" + "ORCHESTRATOR" subtitle + "Settings" text button |
| Empty state | "Rendered Output" card with image icon + "Loaded in Studio Canvas" | plain text "Describe the image and select a workflow to begin." |
| Agent message | orange robot avatar + "Agent · 14:03" + body | "AGENT · READY" label + body, no avatar |
| User message | right-aligned, "You · 14:02" + body | none (no demo user message seeded) |
| Message card style | card with subtle border | bordered card (matches intent) |
| Input row | paperclip icon + textarea + circular orange Send button (paper plane) | textarea + orange "Send prompt" text button (overlaps the input on narrow widths) |
| Extra controls below input | "Speed: F" dropdown, "1:1" aspect ratio dropdown | none — current puts the "Turbo/Quality" and "Base txt2img" selects **above** the input inside the sidebar |

**Files involved:** `ChatSidebar.tsx`, `InputBar.tsx`, `WorkflowSelector.tsx`,
plus their CSS modules. The current state wires lucide-react as a dependency
but does not import any icon yet (see `package.json` line 15).

### 4. Right Panel — Context Assets

| Aspect | Target | Current |
| --- | --- | --- |
| Visibility | always visible (no toggle) | hidden by default, requires clicking the "Assets" rail button |
| Title | "Context Assets" + "Files referenced in this session." description | just "Assets" |
| Item list | 3 hard-coded mock assets (`brand_guidelines.pdf` / `product_shot_01.jpg` / `reference_style.png`) with file-type thumbnails, name, and date | empty list — relies on the user uploading via `<input type="file">` |
| Item style | full-width row, 44px thumbnail, name + meta stacked, no remove button in mock | thumbnail + name + "Remove" button per asset |
| Footer | large centered "+ Upload Asset" CTA | hidden file input + "10MB limit per file" hint |

**Files involved:** `AssetsDrawer.tsx` (default state, content), `uiStore.ts`
(remove the toggle default), mock asset data, new file-type icon component.

### 5. Misc / Off-canvas

- A small blue "N" profile avatar appears in the bottom-right of reality.png
  (probably an artifact of a dev login widget). Not in the target — should be
  removed/relocated.
- The body background in target reads as a slightly warmer brown than
  `--color-bg-base: #1c1917`. `globals.css` line 11 carries a `#1a0f08` fallback
  for `--bg-0` but no component actually defines that variable. Consider
  reconciling to a single semantic token.

---

## Affected Areas

| Path | Why it is affected |
| --- | --- |
| `view2/src/features/generation/components/GenerationStudio.tsx` | Top-level layout — needs to host a new `TopAppBar` and stop wrapping `AssetsDrawer` in a toggle rail |
| `view2/src/features/generation/components/GenerationStudio.module.css` | Two-column → three-column breathing room |
| `view2/src/features/generation/components/WorkspaceCanvas.tsx` | Add tab system, status chip with orange dot, file meta row, dotted-grid background, orange bottom rail |
| `view2/src/features/generation/components/WorkspaceCanvas.module.css` | Dotted grid, new header layout, status dot, action buttons |
| `view2/src/features/generation/components/ChatSidebar.tsx` | Add agent avatar (lucide `Bot`), tweak message meta to "role · HH:MM", attach `Paperclip` icon, swap "Send prompt" text button for a circular `Send` icon button, add Speed + Aspect selects below the input |
| `view2/src/features/generation/components/ChatSidebar.module.css` | New avatar styles, circular send button, sub-input controls row |
| `view2/src/features/generation/components/InputBar.tsx` | Add attachment button, switch button to icon-only, expose Speed/Aspect to parent |
| `view2/src/features/generation/components/InputBar.module.css` | Round send button, attachment button |
| `view2/src/features/generation/components/AssetsDrawer.tsx` | Default to open, render 3 seed mock assets, show file-type icon, "Upload Asset" CTA |
| `view2/src/features/generation/components/AssetsDrawer.module.css` | Wider drawer, asset row layout, CTA footer button |
| `view2/src/features/generation/components/WorkflowSelector.tsx` | Remove from chat sidebar; move Speed/Aspect here or to a new `GenerationControls` row |
| `view2/src/features/generation/stores/uiStore.ts` | `assetsDrawerOpen` likely becomes a constant `true` (or store deleted); add `speed`, `aspectRatio` slices if needed |
| `view2/src/features/generation/stores/generationStore.ts` | No business logic change required, but seed message list moves here for parity with target demo state |
| `view2/src/styles/colors_and_type.css` | Possibly add `--color-accent-glow` / `--color-canvas-dot` tokens, confirm warm brown background, add a circular radius token (`--radius-pill: 999px` if not present) |
| `view2/src/app/globals.css` | Surface the new tokens; expose dotted-grid background utility |
| `view2/src/features/generation/hooks/useGenerationFlow.ts` | No behavior change; just verify the new mock seed messages don't trip validation |
| Tests under `view2/src/features/generation/components/*.test.tsx` | Update snapshots / queries that depend on the old "Send prompt" label, "AGENT · READY" text, hidden assets, or "AWAITING GENERATION" status |

---

## Design System Status

The `colors_and_type.css` token sheet is the **one solid foundation** in place.
The two images use the same warm-dark palette, the same orange accent
(`#d97706`), the same text colors, and a similar font family. The gap is **not**
a token gap — it is a **component composition gap**:

- Tokens that exist and match: `--color-bg-base`, `--color-bg-surface`,
  `--color-accent`, `--color-text-primary`, `--color-text-muted`,
  `--color-border`, `--space-*`, `--radius-sm/md/lg`.
- Tokens missing or underused:
  - No token for a "studio canvas dotted grid" — would need a new
    `--color-canvas-dot` + a `.surface-canvas` utility.
  - `--radius-lg: 100px` works for the input pill but the fully-circular Send
    button would benefit from `--radius-pill: 999px` to make intent explicit.
  - No "status dot" color tied to the `booting` / `generating` state — current
    uses `--color-accent` everywhere.
- Components / patterns missing: a `<TopAppBar />` with tabs + actions, an
  `<IconButton />` primitive, an `<AgentAvatar />` primitive, a `<FileThumb />`
  primitive for PDF/JPG/PNG, and a `<StatusDot />` for the in-progress
  indicator.

The system is **not** what the target is using (the target was likely produced
in Figma without consulting the existing token sheet) — but the token sheet is
**compatible** with the target's palette. A bridging plan can add the missing
naming tokens without changing hue or weight.

---

## Approaches

### Option A — Bridge with the existing design system (recommended)

Add the missing primitives (`TopAppBar`, `IconButton`, `AgentAvatar`,
`FileThumb`, `StatusDot`) and two new utility classes (`.surface-canvas` for
the dotted grid, `.btn-icon-circle` for the circular send). Reuse all existing
tokens. The `AssetsDrawer` becomes always-open and ships with three seeded
mock assets. Workflow/speed/aspect selects move from above the input to a
single `GenerationControls` row below it.

- **Pros:** No palette churn, no rewrites of the stores or hook, plays nicely
  with the existing tests (only assertions + a few new ones), token sheet
  stays the source of truth.
- **Cons:** The new primitives are bespoke and only the test files for them
  will exercise them; no Figma hand-off to keep them in sync.
- **Effort:** Medium.

### Option B — Re-skin everything to the target exactly

Define a new `--color-bg-base: #1a0f08` (warmer brown), a 14/13/12 px type
scale, a new `--space-canvas-pad: 28px`, a custom dotted-grid SVG background,
and rewrite each component to match the target pixel-for-pixel.

- **Pros:** Closest visual match to the expectation image.
- **Cons:** Replaces existing tokens that other code (e.g. tests, generated
  `surface-panel` usages) depends on; risk of regressing the
  integration-test golden expectations (`GenerationStudio.integration.test.tsx`).
- **Effort:** High.

### Option C — Drop a UI library (Radix / shadcn) on top of the tokens

Install a headless component library and rebuild `ChatSidebar`,
`WorkspaceCanvas`, and `AssetsDrawer` using its primitives. Use the existing
tokens to theme them.

- **Pros:** Faster path to a polished feel, accessibility wins for free.
- **Cons:** New dependency, new abstraction layer, more changes to test
  files, conflicts with the project's stated "plain CSS modules + tokens"
  convention.
- **Effort:** Medium-High.

---

## Recommendation

Go with **Option A**. The current codebase already has a working three-pane
layout, a tested Zustand store, and a token sheet that matches the target
palette. The missing work is composition, not foundation: build five small
primitives, change the visibility default on the assets drawer, and re-arrange
the chat input row. This keeps the diff under the 400-line review budget and
keeps the integration tests largely intact.

Concretely the implementation would:

1. Add a `<TopAppBar />` component with tabs (Studio Canvas, Assets),
   status dot + "GENERATING…" text, and Export / Publish action buttons.
2. Add `<AgentAvatar />`, `<StatusDot />`, `<FileThumb />`, `<IconButton />`
   primitives in `view2/src/features/generation/components/primitives/`.
3. Add `.surface-canvas` utility (dotted grid) to `colors_and_type.css` and
   apply it in `WorkspaceCanvas.module.css`.
4. Make the assets drawer the default-open right panel with three seeded
   mock assets (`brand_guidelines.pdf`, `product_shot_01.jpg`,
   `reference_style.png`) and a "+ Upload Asset" footer CTA.
5. Move Speed (Turbo/Quality → "F"/"Q") and Aspect Ratio (1:1, 16:9, 9:16)
   selects to a new `GenerationControls` row **below** the chat input. Remove
   the workflow dropdown from the chat sidebar (the target implies workflow
   selection happens elsewhere, probably on the asset rail).
6. Swap the "Send prompt" text button for a circular icon button with the
   `Send` icon; add a `Paperclip` icon to the left of the textarea.
7. Drop the "N" profile avatar in the bottom right corner (not in target).
8. Add `--radius-pill: 999px` and a `--color-canvas-dot` token.

---

## Risks

- **Test churn:** every component has colocated tests that assert on labels
  and structure. Any rename ("Send prompt" → icon button, "AGENT · READY" →
  "Agent · 14:03", "AWAITING GENERATION" → "GENERATING…") will force test
  updates. The integration test `GenerationStudio.integration.test.tsx` is the
  biggest blast radius.
- **Assets panel default-open regression:** the toggle rail in
  `AssetsDrawer.module.css` is the only way the right column appears today.
  Defaulting it open must not regress narrow viewports; the existing
  `@media (max-width: 1279px) { .drawer { display: none; } }` rule needs
  revisiting to keep mobile usable.
- **Dotted-grid performance:** a pure-CSS radial-gradient background is
  fine, but a tiled SVG/PNG can cause banding on sub-pixel DPR. Validate on
  1x / 2x / 3x displays before shipping.
- **Mock asset hydration:** the seed list needs to come from a constant in
  `view2/src/features/generation/data/mockAssets.ts` (or similar) so it does
  not regress when the user clears the gallery.
- **Profile avatar regression:** the "N" circle in the corner of `realidad.png`
  might be a deliberate auth widget — confirm with the user before deleting.
- **Token rename blast radius:** adding `--color-canvas-dot` and
  `--radius-pill` is additive (safe). Replacing `--color-bg-base` is
  breaking — avoid.

---

## Ready for Proposal

**Yes** — the gap is well-scoped, the affected files are listed, the design
system is mostly aligned, and the recommended approach (Option A) keeps the
diff small and test-friendly. The orchestrator can hand off to
`sdd-propose` for a change named `view2-ui-fix` with the assumptions above
(keep existing tokens, add primitives, make assets drawer default-open, move
controls below input, drop the corner avatar).
