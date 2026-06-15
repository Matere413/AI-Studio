# Proposal: Frontend Architecture Restructure

## Intent

Restructure the small Next.js frontend before it grows: replace flat technical buckets with feature-first boundaries so generation code is easier to navigate, test, and extend without changing product behavior.

## Scope

### In Scope
- Move generation-specific UI, API, store, hooks, types, CSS modules, and tests under `view/src/features/generation/`.
- Move reusable UI primitives under `view/src/shared/components/ui/`.
- Extract generation orchestration from `Sidebar` into a feature hook while preserving HTTP, WebSocket, retry, preview, and gallery behavior.
- Centralize repeated `next/image` test mocking and remove unused template CSS.

### Out of Scope
- Product, API, WebSocket, image-serving, or visual behavior changes.
- Backend changes or new generation capabilities.
- Full Clean Architecture layering or additional abstraction ceremony.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- None. Existing `generative-ai-studio-frontend` and `image-generation` behavior requirements remain unchanged.

## Approach

Adopt the exploration recommendation: feature-first / screaming architecture. Use `features/generation` for domain code, `shared` for reusable primitives, and keep `app` thin. Prefer file moves plus import updates first, then a focused hook extraction for generation flow orchestration.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `view/src/app/page.tsx` | Modified | Update import to the generation studio entry component. |
| `view/src/components/studio/*` | Moved/Modified | Relocate generation components and tests; promote shared primitive. |
| `view/src/lib/api.ts` | Moved | Move generation API/WS helpers into the feature. |
| `view/src/stores/generationStore.ts` | Moved | Keep store contract while placing it in the generation feature. |
| `view/src/test/setup.ts` | Modified | Centralize shared test mocks. |
| `view/src/app/page.module.css` | Removed | Delete unused Next.js template CSS. |
| `openspec/changes/frontend-architecture-restructure/proposal.md` | New | Records proposal contract. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Import churn breaks tests | Medium | Move in small steps and run frontend tests/type checks. |
| Refactor accidentally changes generation flow | Medium | Preserve existing tests around submit, WebSocket, retry, preview, and history. |
| Diff exceeds review budget if renames are not detected | Medium | Split delivery into move-only and hook-extraction slices if needed. |

## Rollback Plan

Revert the restructure commit(s) to restore the flat `view/src/components/studio`, `view/src/lib/api.ts`, and `view/src/stores/generationStore.ts` layout. No data migration is required because behavior and persisted state are unchanged.

## Dependencies

- Existing `@/*` TypeScript alias in `view/tsconfig.json`.
- Existing frontend test suite and Next.js 16 project conventions.

## Success Criteria

- [ ] Generation submission, WebSocket lifecycle, retry handling, image preview, and session history behave the same as before.
- [ ] Domain code lives under `view/src/features/generation/`; reusable UI lives under `view/src/shared/`.
- [ ] Frontend tests/type checks pass after the restructure.
- [ ] Implementation diff respects the 400-line review budget or is split before apply.
