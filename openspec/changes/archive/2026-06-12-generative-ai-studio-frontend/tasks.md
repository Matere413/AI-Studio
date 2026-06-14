# Tasks: Generative AI Studio Frontend

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 520-700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: shell/store/api wiring → PR 2: gallery/polish/tests |
| Delivery strategy | ask-always |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Studio shell, state, and API plumbing | PR 1 | Base = main; include page/layout rewrites and core store helpers. |
| 2 | Interactive UI sections and generation flow | PR 2 | Base = PR 1; add sidebar/canvas/log/progress and wiring. |
| 3 | History gallery, validation, and verification | PR 3 | Base = PR 2; finish client history + tests/manual checks. |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Update `view/src/app/layout.tsx` to remove `next/font/google`, keep local Matere fonts, and refresh metadata.
- [x] 1.2 Add `zustand` to `view/package.json` and create `view/src/stores/generationStore.ts` with the contract from the spec.
- [x] 1.3 Create `view/src/lib/api.ts` with `submitGenerate()` and `getWsUrl()` for `/api/generate` and `/api/ws/generate/{job_id}`.

## Phase 2: Core Implementation

- [x] 2.1 Replace `view/src/app/page.tsx` starter content with `StudioLayout` and simplify `view/src/app/page.module.css`.
- [x] 2.2 Create `view/src/components/studio/StudioLayout.tsx` and scoped CSS Modules for the desktop grid + stacked mobile layout.
- [x] 2.3 Implement `Sidebar.tsx`, `Canvas.tsx`, `TerminalLog.tsx`, and `PixelProgressBar.tsx` with prompt, controls, status, and progress states.
- [x] 2.4 Add `ImageGallery.tsx` for newest-first client-side history, truncated prompt text, and empty-state fallback.

## Phase 3: Integration / Wiring

- [x] 3.1 Wire sidebar actions to `generationStore` mutations and form validation rules from the spec.
- [x] 3.2 Connect `submitGenerate()` → `startConnecting()` → WebSocket event handling → `sessionHistory` prepend/reset.
- [x] 3.3 Add `view/next.config.ts` rewrites for `FASTAPI_ORIGIN` so `/api/*` proxies to FastAPI in dev.

## Phase 4: Testing / Verification

- [x] 4.1 Verify store transitions for idle/connecting/generating/done/error, cancel, and completed-to-history behavior.
- [x] 4.2 Verify `submitGenerate()` payload, `getWsUrl()` output, and retry/backoff handling for `/api/ws/generate/{job_id}`.
- [x] 4.3 Manually check desktop/mobile layout, cold-start terminal copy, prompt validation, and gallery rendering against the spec scenarios.

## Phase 5: Cleanup / Documentation

- [x] 5.1 Remove any starter-page leftovers and dead CSS after the studio shell is in place.
- [x] 5.2 Update comments/docstrings only where needed to clarify store/event contracts.