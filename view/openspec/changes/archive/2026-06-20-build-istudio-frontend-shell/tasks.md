# Tasks: Build I-Studio Frontend Shell

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,250 (5 PRs) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → 2 → 3 → 4 → 5 |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Work Units

| # | Goal | PR | ~loc |
|---|------|----|------|
| 1 | Bootstrap | PR 1 | 250 |
| 2 | Tokens + primitives | PR 2 | 300 |
| 3 | Shell composition | PR 3 | 350 |
| 4 | Feature facades | PR 4 | 150 |
| 5 | UX/a11y polish | PR 5 | 200 |

## Phase 1: Bootstrap

- [x] 1.1 Create `package.json` — Next.js 14, React 18, Tailwind v3
- [x] 1.2 Create `tsconfig.json` — strict, `@/*` → `src/*`
- [x] 1.3 Create `tailwind.config.ts` — DESIGN.md tokens
- [x] 1.4 Create `postcss.config.js`, `next.config.js`, `.eslintrc.json`, `.prettierrc`
- [x] 1.5 Create `src/app/globals.css` — reset, `@tailwind`
- [x] 1.6 Create `src/app/layout.tsx` — html lang, metadata
- [x] 1.7 Create `src/app/page.tsx` — empty placeholder
- [x] 1.8 Verify: `pnpm dev` → dark page at localhost:3000

## Phase 2: Tokens & Primitives

- [x] 2.1 Create `src/shared/presentation/icons.tsx` — SVG constants, stroke 1.5
- [x] 2.2 Create `button.tsx` — primary/secondary/ghost variants
- [x] 2.3 Create `icon-button.tsx` — required `aria-label`
- [x] 2.4 Create `input.tsx` — dark theme, focus ring
- [x] 2.5 Create `pill-select.tsx`, `avatar-mark.tsx`
- [x] 2.6 Create `index.ts` — barrel export
- [x] 2.7 Verify: Button + Input render, tokens match DESIGN.md

## Phase 3: Shell Composition

- [x] 3.1 Create `src/shared/presentation/mock-data.tsx` — messages, assets, status
- [x] 3.2 Rewrite `src/app/page.tsx` — `'use client'`, aside 300px / main / aside 260px
- [x] 3.3 Add `<aside aria-label="Agent Chat">`
- [x] 3.4 Add `<main>` studio — topbar, canvas, status
- [x] 3.5 Add `<aside aria-label="Context Assets">`
- [x] 3.6 Verify: screenshot vs reference.html at 1280px

## Phase 4: Feature Facades

- [x] 4.1 Create `src/features/chat/presentation/components/ChatSidebar.tsx`
- [x] 4.2 Create `ChatComposer.tsx` — textarea + send
- [x] 4.3 Create `MessageList.tsx` — `<time dateTime>`
- [x] 4.4 Create `src/features/studio/presentation/components/StudioTopBar.tsx` — `role="tablist"`
- [x] 4.5 Create `StudioCanvas.tsx`, `StatusBar.tsx` — `aria-live="polite"`
- [x] 4.6 Create `src/features/assets/presentation/components/AssetsDrawer.tsx`, `AssetList.tsx`
- [x] 4.7 Update `page.tsx` — use feature components
- [x] 4.8 Create empty barrels: `src/features/{chat,studio,assets}/{domain,application,infrastructure}/` (visible features only; `auth` and `workflows` scaffolding removed post-review — out of scope per proposal)
- [x] 4.9 Verify: no visual regression

## Phase 5: UX/A11y Polish

- [x] 5.1 Add drawer toggle in `page.tsx` — `aria-expanded`, conditional render
- [x] 5.2 Add responsive default — `hidden lg:block` on AssetsDrawer
- [x] 5.3 Add Enter-to-send / Shift+Enter in `ChatComposer.tsx`
- [x] 5.4 Add `prefers-reduced-motion` rule in `globals.css`
- [x] 5.5 Add dotted canvas pattern in `StudioCanvas.tsx` (SVG-based, no CSS gradients)
- [x] 5.6 Verify: responsive breakpoints, a11y landmarks, reduced motion, no-ops — automated contract checks via `pnpm run test:contract` (Playwright: drawer ARIA, tablist/tab/tabpanel, resize bidirectionality, user override preservation, ChatComposer no-ops, zero API calls). Manual/browser-only checks (reduced motion, visual pattern, a11y landmark audit) listed separately in apply-progress.
