# Exploration — build-istudio-frontend-shell

## Current State

**Project root (`/Users/matere/Documents/Preguntas/Fornt`):**

- `AGENTS.md` — stack, hexagonal feature-first architecture, dependency rules, naming conventions.
- `DESIGN.md` — canonical I-Studio design system mapped to Tailwind v3+ (colors, spacing, typography, motion, anti-patterns, full `tailwind.config.js`).
- `reference.html` — self-contained, browser-ready visual reference matching `DESIGN.md` exactly. No external dependencies, no JSX/Babel, SVG icons only.
- `openspec/config.yaml` — SDD/OpenSpec config: `artifact_store: openspec`, force-chained PR strategy, 400-line review budget, no test runner, no build, no lint, no type-checker.
- `openspec/specs/` and `openspec/changes/` — empty scaffolds (`gitkeep` only).
- `.atl/skill-registry.md` — project-level skill index.
- `.playwright-cli/` — two prior browser snapshots of `reference.html`; no other source code.

**What does NOT exist yet:**

- No `package.json`, no `tsconfig.json`, no `tailwind.config.js`, no `postcss.config.js`, no `next.config.*`.
- No `src/`, no `app/`, no `middleware.ts`, no `.eslintrc`, no `.prettierrc`.
- No `node_modules`, no lockfile, no test runner, no Playwright config.
- Original `ds-i-studio-plataforma-de-marketing-design-system/` directory and the reference image were deleted by the user to reduce noise (confirmed in the most recent session prompt). `reference.html` + `DESIGN.md` are now the single source of truth for visuals.

**Visual reference decoded (from `reference.html` + Playwright a11y tree):**

| Region | Anatomy |
| --- | --- |
| Sidebar (left, 300px) | `<aside aria-label="Agent Chat">` → topbar (Agent mark + "Agent Chat" + settings icon button) → `<section aria-label="Messages">` with `<article>` message blocks (user right, agent left) → footer with pill composer (attach + textarea + send) + quick controls (Speed, Aspect Ratio). |
| Main (right) | `<main>` → topbar 48px with workspace title + `<button role="tab" aria-selected>` "Studio Canvas" + actions (`Assets` collapsed/expanded, `Export`, `Publish` primary) → canvas meta strip with mono filename + zoom icons → canvas stage with dotted background, "GENERATING..." status with pulse, and a 1:1 output frame containing a placeholder thumbnail + caption. |
| Assets drawer (right, 260px) | `<aside aria-label="Context Assets">` with header, asset rows (icon + name + date), and a footer "Upload Asset" button. |

**Hexagonal feature-first map (from `AGENTS.md`):** auth, studio, chat, workflows, assets. Each has `domain/`, `application/`, `infrastructure/`, `presentation/{components,pages}`.

## Affected Areas

The change scaffolds the entire project — every "affected area" is new. Listing them as a target surface, not a modification set:

- `package.json` — Next.js 14+, React 18+, TypeScript 5+, Tailwind v3+, ESLint, Prettier. Scripts: `dev`, `build`, `start`, `lint`, `typecheck`, `test` (Vitest, no tests yet).
- `tsconfig.json` — strict mode, `paths` for `@/*` → `src/*`.
- `tailwind.config.js` — full `DESIGN.md` token block (colors, fontFamily, fontSize, spacing, borderRadius, transitionTimingFunction, transitionDuration, letterSpacing).
- `postcss.config.js` — Tailwind + autoprefixer.
- `src/app/layout.tsx` — root layout, dark mode, font-smoothing, lang="en".
- `src/app/globals.css` — Tailwind directives + base reset.
- `src/app/page.tsx` — Home route. Should render the shell via feature `presentation/pages/`.
- `src/middleware.ts` — stub with no-op auth (deferred to a later change; AGENTS.md mentions it but auth is out of shell scope).
- `src/shared/presentation/components/` — Button, IconButton, Input, PillSelect, AvatarMark. Server-compatible RSC primitives.
- `src/shared/presentation/icons/` — agent mark, paperclip, send, settings, image, file, asset, search-minus, fit-to-screen, etc. (SVG components).
- `src/features/{chat,studio,assets,workflows,auth}/` — directory tree with empty barrel files, ready for follow-up changes.
- `src/features/chat/presentation/components/` — `ChatSidebar`, `ChatTopbar`, `MessageList`, `MessageBubble`, `Composer`.
- `src/features/studio/presentation/components/` — `WorkspaceTopbar`, `StudioCanvas`, `CanvasMeta`, `CanvasStage`, `OutputFrame`, `StatusPill`.
- `src/features/assets/presentation/components/` — `AssetsDrawer`, `AssetList`, `AssetRow`.
- `openspec/specs/{app-shell,design-tokens}/spec.md` — new delta specs (the source-of-truth for the shell's required behavior).

**No existing code to refactor or migrate.** The risk profile is "greenfield + visual fidelity," not "rewrite."

## Approaches

### Approach A — Chained PRs by concern (RECOMMENDED)

Slice the work so each PR is reviewable in isolation and respects the 400-line budget.

1. **PR1 — Bootstrap (~250 lines):** `package.json`, `tsconfig.json`, `next.config.mjs`, `postcss.config.js`, `tailwind.config.js`, `.eslintrc.cjs`, `.prettierrc`, `.gitignore`, `src/app/layout.tsx`, `src/app/globals.css`, `src/app/page.tsx` (empty). Result: `pnpm dev` boots a dark page with the I-Studio background color. No visual content yet.
2. **PR2 — Shared design system + icons (~300 lines):** `src/shared/presentation/components/{Button,IconButton,Input,PillSelect,AvatarMark}.tsx` and `src/shared/presentation/icons/*.tsx`. Tokens-only — no feature composition. Result: primitives are usable from stories (none yet) and from feature PRs.
3. **PR3 — App shell composition (~350 lines):** the chat sidebar + main canvas + assets drawer pure presentational components, wired into `app/page.tsx`. Mock data inline (the strings in `reference.html`). Result: pixel-equivalent of `reference.html` rendered, no state, no fetch.
4. **PR4 — Hexagonal feature skeletons (~150 lines):** create `domain/`, `application/`, `infrastructure/`, `presentation/{components,pages}/` directories under each of the five features with barrel `index.ts` files. Establishes the dependency direction and the future home for real logic.
5. **PR5 — First interaction polish (~200 lines):** small UX improvements the user explicitly allowed — proper `role="tablist"`, `aria-live` on status, collapsible assets drawer with state, `Enter` to send, `<time>` for timestamps, `prefers-reduced-motion` for pulse/scan. Result: shell is interactive and accessible without feature logic.

- **Pros:** Each PR is reviewable alone. Tokens (PR1–2) are stable before composition (PR3). Hexagonal structure (PR4) lands on a known-working shell. UX polish (PR5) is diffable against a clean visual baseline. Easy to revert any single slice. Aligns with `work-unit-commits` and `chained-pr` skills.
- **Cons:** Five PRs to land before any "real" feature. Requires disciplined sequencing in the orchestrator.
- **Effort:** Medium (5 sessions, well-scoped).

### Approach B — Single "shell + tokens" PR

Land PR1+PR2+PR3 in one PR, around 800–1000 lines.

- **Pros:** Faster time-to-visible-shell. One branch, one review.
- **Cons:** **Violates the 400-line budget** the user explicitly set. Reviewer fatigue is real; a 900-line PR for a brand-new project gets rubber-stamped. Hard to revert partial work. Hurts the audit trail.
- **Effort:** Low implementation, High review cost.

### Approach C — Chained PRs by feature

Bootstrap (PR1) + Chat feature end-to-end (PR2) + Studio feature (PR3) + Workflows (PR4) + Assets (PR5).

- **Pros:** Each PR yields a usable feature slice.
- **Cons:** First three PRs need to invent tokens, primitives, and shell scaffolding simultaneously because there is no design-system PR. The shell's visual baseline is unstable during review. Reviewers have to recheck visual diffs every time.
- **Effort:** Medium-high.

### Comparison

| Approach | Review cost | Time to shell | Reversibility | Audit quality |
| --- | --- | --- | --- | --- |
| A — by concern | Low (5 × ≤400) | ~3 PRs in | Per slice | High |
| B — single mega | High (~900) | 1 PR | All-or-nothing | Low |
| C — by feature | Medium | ~2 PRs in | Per feature | Medium |

## Recommendation

**Approach A (chained PRs by concern).** It is the only option that respects the user's explicit force-chained / 400-line budget. It also matches the project philosophy: the design system and the hexagonal skeleton are durable, the shell composition is reviewable against `reference.html`, and the small UX improvements (proper ARIA, `aria-live`, `<time>`, `prefers-reduced-motion`, collapsible drawer) sit in a focused last PR where the diff is small and intentional.

Specifically for the **shell slice (PR3):** the presentational components stay RSC-friendly (no `"use client"` unless interactive), the chat message list uses `<article>` + `<time>`, the "Studio Canvas" tab uses a proper `role="tablist"` (small upgrade from `role="tab"` on a lone button in the reference), the assets drawer becomes collapsible with `aria-expanded` reflecting state, and the status pill gets `aria-live="polite"` so screen readers announce generation completion.

**Allowed small UX improvements (caller-stated allowance):**

1. **Assets drawer is collapsible.** The reference shows it open; the action button label and `aria-expanded` are already there. Add a client-side state hook (`useUiStore` or React `useState` lifted to the page) so the button toggles the drawer. Improvement: reviewer can hide the drawer on narrow viewports.
2. **Composer keyboard support.** Enter sends, Shift+Enter inserts a newline. `aria-keyshortcuts` on the send button. Improvement: standard chat UX, free win.
3. **Status announcement.** `aria-live="polite"` on the "GENERATING..." → "COMPLETED in 12.4s" status. Improvement: a11y for low-vision users.
4. **Tab pattern.** Wrap "Studio Canvas" in a `role="tablist"` with at least one additional tab placeholder ("Workflow", "History") so the pattern is real, not a decorative one-tab control. Improvement: keyboard navigation, a11y, and pre-built room for future features.
5. **`<time>` for message timestamps.** `You • 14:02` becomes `You <time dateTime="14:02">14:02</time>`. Improvement: semantic HTML, future i18n-friendly.
6. **`prefers-reduced-motion`.** Disable the pulse animation and any future scan-line. Improvement: respects OS-level a11y setting.
7. **Dotted canvas background as a token.** Move the `radial-gradient` from inline CSS to a Tailwind utility or CSS variable in `globals.css` so designers can tune it. Improvement: token discipline.

These are the only deviations from `reference.html`. The shell's *look* must remain pixel-equivalent otherwise.

**Stack pinning (proposal-phase decision, not now):**

- Next.js: latest 14.x at time of execution.
- React: 18.x (Next 14 default).
- TypeScript: 5.x strict.
- Tailwind: 3.4.x (DESIGN.md specifies v3+).
- Node: 20 LTS.
- Package manager: pnpm (user has used pnpm in past projects; confirm in proposal).
- Lint: ESLint flat config or `next/core-web-vitals`.
- Test: Vitest + RTL wired but with zero tests in this change (deferred to a follow-up "test scaffolding" change so this change stays under 400 lines).

## Risks

- **400-line budget pressure.** Tailwind config + 5 SVG icons + 6 primitives + the shell composition is naturally 800+ lines. The chained PR plan mitigates this but the proposal must commit to per-PR line budgets. The orchestrator should forecast per-PR sizes before apply.
- **No executable test/build/lint commands.** `openspec/config.yaml` confirms this. `sdd-verify` will report verification as **blocked**. The proposal must declare a manual-verification protocol (e.g., `pnpm dev` renders the shell pixel-equivalent to `reference.html`, screenshot diff, Playwright a11y snapshot matches the existing trace) and treat that as the success criterion for this change.
- **Hexagonal overhead in a greenfield repo.** The folder-per-feature-with-four-subfolders structure can feel premature. The proposal must argue that the structure is cheap to scaffold (~150 lines of `index.ts` barrels) and pays off from feature #1.
- **No git remote, no CI.** Force-chained PR strategy implies PRs. If the user has no remote configured, the chained strategy degenerates into chained local commits. The proposal must confirm whether the user wants PRs to a remote or chained local feature branches on `main`.
- **Visual fidelity drift.** `reference.html` uses an inline `<style>` with non-tokenized values (`#111` for the output frame background, `rgb(217 119 6 / 5%)` for the overlay gradient). If the proposal does not explicitly tokenize these, the design system will have two parallel color sets. Recommend adding a `canvas.frame` token and an `accent.glow` token in `globals.css`.
- **Dark-mode-only assumption.** `DESIGN.md` says "dark mode always." The proposal must lock that — no `dark:` variant utilities, no theme toggle.
- **CSS in `reference.html` uses `border` shorthand on `border-color` only.** Tailwind utility `border-border` already maps to 1px, so the only translation risk is `border-bottom: 2px solid var(--color-accent)` on the tab, which is a custom class in the shell, not a stock Tailwind utility.
- **Icon consistency.** The reference uses inline `<svg>` with mixed `stroke-width` (1.5, 1.7, 1.8, 2). DESIGN.md says 1–1.5px. The proposal must mandate a 1.5px default and let individual icons override only when geometry demands it.
- **Empty feature folders.** Five features × four subfolders × barrel files = 20 empty-ish files. Risk of npm/pnpm `files` warnings and reviewer confusion. The proposal should keep barrels to one-liner re-exports and add a `README.md` in `features/` explaining the convention.
- **Tone drift from DESIGN.md anti-patterns.** The reference is already compliant (dark, borders, SVG-only, no gradients beyond a 5% accent overlay, no rounded fonts). The proposal must restate the anti-patterns in the spec so the apply phase cannot drift.

## Ready for Proposal

**Yes — the proposal phase has enough context to start.**

The orchestrator should hand the user these clarifying questions before launching `sdd-propose` (one round, batched — not a menu):

1. **Package manager:** pnpm (recommended, matches prior projects) or npm or yarn?
2. **PR target:** real GitHub remote, or chained local feature branches off `main`?
3. **Scope of "shell":** (a) pure static shell with mock data from `reference.html`, or (b) static shell + one interaction wired (assets drawer toggle, composer Enter-to-send)? Recommendation: (a) for PR3, (b) in PR5.
4. **Auth in this change:** stub the middleware with a no-op, or omit middleware entirely? AGENTS.md mentions `middleware.ts` but auth is out of scope.
5. **Five features all scaffolded in PR4, or only the visible three (chat, studio, assets) and add workflows/auth later?** Recommendation: all five — the directory cost is ~150 lines and the architectural promise is delivered.

If the user answers "go ahead with your recommendations on all five" the proposal can be drafted with those defaults pre-applied. If the user wants to deviate, capture the deviation and let the proposal reflect it.

**Next phase:** `sdd-propose` with the chained PR plan, the token-extension decisions, the explicit UX-improvement deltas (collapsible drawer, `aria-live`, `role="tablist"`, `<time>`, `prefers-reduced-motion`, Enter-to-send), and a manual-verification protocol (since `verify` is `blocked` per `config.yaml`).
