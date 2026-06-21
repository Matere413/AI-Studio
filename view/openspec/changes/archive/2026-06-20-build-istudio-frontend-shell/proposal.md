# Proposal: Build I-Studio Frontend Shell

## Intent

Build the I-Studio frontend shell — a pixel-equivalent implementation of `reference.html` using Next.js 14+, TypeScript strict, and Tailwind CSS v3. Establishes project scaffold, design tokens, shared UI primitives, and the three-region layout (chat sidebar, studio canvas, assets drawer) with mock data. Foundation for all future features.

## Scope

### In Scope
- Project bootstrap: Next.js 14, TS strict, Tailwind v3, pnpm, ESLint, Prettier
- Design tokens: `tailwind.config.js` from DESIGN.md, `globals.css`, reset, tokenized dotted canvas
- Shared primitives: Button, IconButton, Input, PillSelect, AvatarMark (SVG-only, RSC-compatible)
- Three-region layout: chat sidebar (300px), studio canvas (fluid), assets drawer (260px, collapsible)
- Facades: mock messages + composer (chat), workspace topbar + canvas stage + output frame (studio), asset list + upload button (assets)
- UX deltas from reference: responsive drawer default, `aria-live` status, `role="tablist"`, `<time>` timestamps, `prefers-reduced-motion`, SVG-only icons (1.5px stroke), Enter-to-send
- Hexagonal feature scaffold: `src/features/{chat,studio,assets,auth,workflows}/` with empty barrels

### Out of Scope
- Real chat logic, backend/API, auth, workflow library, upload persistence, real asset management
- Tests (Vitest/RTL deferred), CI/CD, git remote

## Capabilities

> `openspec/specs/` is empty — no existing specs to modify.

### New Capabilities
- `app-shell`: Three-region layout, responsive breakpoints, accessible region semantics, keyboard navigation
- `design-tokens`: Tailwind config + CSS custom properties, global reset, shared component primitives

### Modified Capabilities
None.

## Approach

Approach A — chained PRs by concern (respects 400-line budget):

1. **PR1 (~250 loc):** Bootstrap — configs, `src/app/layout.tsx`, `globals.css`, empty `page.tsx`
2. **PR2 (~300 loc):** Shared primitives + SVG icons in `src/shared/presentation/`
3. **PR3 (~350 loc):** Shell composition — chat + canvas + assets in `page.tsx`, mock data
4. **PR4 (~150 loc):** Hexagonal feature barrels for all 5 features
5. **PR5 (~200 loc):** UX polish — ARIA semantics, responsive drawer, motion, keyboard support

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| Project root | New | `package.json`, `tsconfig`, config files |
| `src/app/` | New | Layout, globals, home page |
| `src/shared/presentation/` | New | Primitives + SVG icons |
| `src/features/{chat,studio,assets}/presentation/` | New | Facade components |
| `src/features/{auth,workflows}/` | New | Empty hexagonal scaffold |
| `openspec/specs/{app-shell,design-tokens}/` | New | Spec contracts |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Visual drift from reference | Medium | Screenshot diff per PR |
| 400-line budget pressure | High | Chained PR plan |
| No test/lint commands | High | Manual verify: `pnpm dev` + visual compare |

## Rollback Plan

Per-chained-PR revert on its own branch. PR1 revert invalidates downstream PRs — rebase or replay.

## Dependencies

- pnpm, Node.js 20 LTS
- `reference.html` + `DESIGN.md` as visual source of truth

## Success Criteria

- [ ] `pnpm dev` renders dark page at `localhost:3000` matching `reference.html`
- [ ] Three-region layout responsive: assets drawer collapsed ≤768px, open ≥1024px
- [ ] No emoji icons, gradients, or shadows — SVG-only with 1.5px stroke
- [ ] `aria-live="polite"` on status, `role="tablist"` on tabs, `<time>` on timestamps
- [ ] `prefers-reduced-motion` disables pulse animation
