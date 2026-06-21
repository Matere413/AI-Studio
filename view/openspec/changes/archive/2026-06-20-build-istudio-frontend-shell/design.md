# Design: Build I-Studio Frontend Shell

## Technical Approach

Greenfield Next.js 14+ App Router bootstrap with TypeScript strict and Tailwind v3. Single `page.tsx` composes three facade regions (chat, studio, assets) from mock data — no backend, auth, or persistence. Design tokens map DESIGN.md hex values 1:1 into `tailwind.config.ts`. Shared primitives (`Button`, `IconButton`, `Input`, `PillSelect`, `AvatarMark`) live in `src/shared/presentation/` — a complement to AGENTS.md's feature-layer `presentation/` pattern. Facade components occupy each feature's `presentation/components/` directory. Auth and workflows features get empty hexagonal barrels only.

## Architecture Decisions

### Decision: Single page.tsx with client boundary at page level

| Option | Tradeoff | Decision |
|--------|----------|----------|
| RSC-only page, client islands per region | More boilerplate, no benefit for pure facade | Rejected |
| `'use client'` on page.tsx | Loses RSC benefits, simpler for interactive shell with drawer toggle state | **Chosen** |
| Per-region client boundaries | Preserves partial RSC, overengineered for mock data | Rejected |

**Rationale**: The drawer toggle and composer `onKeyDown` require client-side state. Since every region is a visual facade with no data fetching, the entire page mounts as a client component. Individual primitives like `Button` and `Input` remain server-compatible — they wrap standard HTML elements without internal state.

### Decision: SVG icons as module-level constants, not per-icon components

**Choice**: Single `icons.tsx` exporting named `React.JSX.Element` constants.
**Rationale**: Avoids per-icon import overhead, matches reference.html's inline SVG pattern, keeps file count low for ≤400-line PR budget. Each icon uses `stroke-width="1.5"` per design-tokens spec.

### Decision: CSS-driven drawer default, React toggle

**Choice**: Tailwind `hidden lg:block` controls initial visibility; React `useState` + `aria-expanded` on toggle button handles user control.
**Rationale**: CSS breakpoint matches spec requirements (collapsed ≤768px, open ≥1024px) without JS media queries. React state enables explicit toggle without losing CSS-driven defaults on resize.

### Decision: Mock data in shared/presentation, not infrastructure

**Choice**: `src/shared/presentation/mock-data.tsx` exports `const` arrays.
**Rationale**: No API, no persistence, no infrastructure layer. For this facade-only change, placing mock data beside components avoids premature abstraction. Future real data flows into `features/*/infrastructure/`.

### Decision: `src/shared/presentation/` for design primitives

**Choice**: Extends AGENTS.md hexagonal structure with a shared presentation layer.
**Rationale**: AGENTS.md defines `presentation/` only at the feature level, but design tokens require reusable primitives that belong to no single feature domain. This is the minimal extension — primitives are pure presentational with zero domain logic.

## Data Flow

```
mock-data.ts (const arrays) ──► page.tsx ('use client')
                                    ├──► ChatSidebar (messages + composer)
                                    ├──► StudioCanvas (header + stage + status)
                                    └──► AssetsDrawer (conditional, toggled)
```

No cross-feature data flow. Each facade component receives its data via props from `page.tsx`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `package.json` | Create | Next.js 14, React 18, Tailwind v3, pnpm workspace |
| `tsconfig.json` | Create | strict mode, paths alias `@/*` → `src/*` |
| `tailwind.config.ts` | Create | DESIGN.md tokens (colors, fonts, spacing, radius, easing) |
| `postcss.config.js` | Create | Tailwind + autoprefixer |
| `next.config.js` | Create | Minimal config |
| `.eslintrc.json` | Create | ESLint + Prettier integration |
| `.prettierrc` | Create | Project formatting rules |
| `src/app/globals.css` | Create | Reset, `@tailwind` directives, reduced-motion media query |
| `src/app/layout.tsx` | Create | Root layout: `<html lang="en">`, metadata, font smoothing |
| `src/app/page.tsx` | Create | Full shell composition (`'use client'`, three regions, drawer state) |
| `src/shared/presentation/icons.tsx` | Create | SVG icon constants (1.5px stroke) |
| `src/shared/presentation/button.tsx` | Create | Button: primary/secondary/ghost variants |
| `src/shared/presentation/icon-button.tsx` | Create | IconButton: `aria-label` required |
| `src/shared/presentation/input.tsx` | Create | Input: dark theme, focus ring |
| `src/shared/presentation/pill-select.tsx` | Create | PillSelect: `<select>` styled as pill |
| `src/shared/presentation/avatar-mark.tsx` | Create | AvatarMark: accent circle with SVG |
| `src/shared/presentation/mock-data.tsx` | Create | Mock messages, assets, status |
| `src/shared/presentation/index.ts` | Create | Barrel export |
| `src/features/chat/presentation/components/*.tsx` | Create | Chat facade: header, messages, composer |
| `src/features/studio/presentation/components/*.tsx` | Create | Studio facade: topbar, canvas, status |
| `src/features/assets/presentation/components/*.tsx` | Create | Assets facade: drawer, items, upload button |
| `src/features/{chat,studio,assets,auth,workflows}/{domain,application,infrastructure}/index.ts` | Create | Empty hexagonal barrels (15 files) |

## Interfaces / Contracts

```typescript
// Button variants
type ButtonVariant = 'primary' | 'secondary' | 'ghost';

// IconButton — aria-label is mandatory for accessibility
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  'aria-label': string;
  children: React.ReactNode; // SVG icon element
}

// Mock message shape
interface MockMessage {
  role: 'user' | 'agent';
  text: string;
  time: string; // e.g. "14:03"
  card?: { title: string; subtitle: string };
}
```

## Testing Strategy

No test runner or package scripts exist (`openspec/config.yaml` confirms no Vitest/RTL/Playwright installed). Verification is manual per chained PR:

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Visual | Pixel match vs reference.html | Manual `pnpm dev`, side-by-side screenshot compare |
| Responsive | Drawer at 375/768/1024/1440px | Browser resize + visual check |
| Accessibility | Landmarks, `aria-expanded`, `aria-live`, tab order | Manual keyboard nav + VoiceOver |
| Motion | Reduced motion disables pulse | Toggle OS setting, verify |

**Planned future commands**: `pnpm lint`, `pnpm type-check`, `pnpm test` (Vitest), `pnpm test:e2e` (Playwright).

## Migration / Rollout

No migration required — greenfield project. Rollback: revert each chained PR independently. PR1 revert invalidates downstream PRs; rebase or replay.

## Open Questions

None. All decisions are constrained by reference.html, DESIGN.md, and the approved proposal specs.
