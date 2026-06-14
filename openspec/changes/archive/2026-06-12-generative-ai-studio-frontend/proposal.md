# Proposal: Generative AI Studio Frontend

## Intent

Create a desktop-first Generative AI Studio UI using the Matere design system. The frontend must let users configure generation inputs, submit jobs to the FastAPI/Modal backend, observe WebSocket generation progress, and review session outputs without adding auth or backend workflow changes.

## Scope

### In Scope
- Next.js App Router studio page with Matere tokens, local fonts, chunky borders, CRT/terminal styling.
- 340px input sidebar, main output canvas, terminal log in `VT323`, pixel progress bar, and session history gallery.
- Zustand store for prompt/parameters, current job, WebSocket events, generation state, and local session history.
- Next.js rewrites for `/api/generate` and `/api/ws/generate/:job_id` to integrate with FastAPI during local/dev flows.

### Out of Scope
- Authentication, accounts, multi-user saved galleries, or billing.
- Mobile-first redesign; MVP may include basic stacking but targets desktop first.
- Backend generation contract changes beyond integration configuration.

## Capabilities

### New Capabilities
- `generative-ai-studio-frontend`: User-facing studio shell for configuring, submitting, monitoring, and browsing image-generation sessions.

### Modified Capabilities
- None. Existing `image-generation` API/WebSocket behavior is consumed but not changed.

## Approach

Replace the starter Next.js page with a single-page studio composed from focused components. Use Zustand for async-friendly generation state and a small API/WebSocket layer that posts to `/api/generate`, then streams `JobEvent` updates from `/api/ws/generate/{job_id}`. Configure `next.config.ts` rewrites to hide backend origin in development while preserving the FastAPI contract.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `view/src/app/layout.tsx` | Modified | Remove Google font dependency; use Matere/local fonts and metadata. |
| `view/src/app/page.tsx` | Modified | Replace starter UI with studio composition. |
| `view/src/components/studio/` | New | Sidebar, canvas, terminal log, progress bar, history gallery. |
| `view/src/stores/generationStore.ts` | New | Zustand state for generation/session lifecycle. |
| `view/src/lib/api.ts` | New | Generate request + WebSocket URL helpers. |
| `view/next.config.ts` | Modified | Add FastAPI HTTP/WebSocket rewrites. |
| `view/package.json` | Modified | Add `zustand`. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| WebSocket rewrites may not suit serverless production | Med | Treat rewrites as dev/local path; keep direct backend URL option later. |
| Modal cold starts feel stalled | Med | Show terminal messages and indeterminate progress before numeric progress arrives. |
| Session history persistence assumptions | Low | Keep MVP history client-side only. |

## Rollback Plan

Revert frontend files and `zustand` dependency; restore starter `page.tsx` and remove rewrites. Backend remains unchanged.

## Dependencies

- Existing FastAPI `POST /generate` and `WS /ws/generate/{job_id}` contracts.
- Matere design system CSS/fonts already imported under `view/`.
- `zustand` runtime dependency.

## Success Criteria

- [ ] User can submit a prompt/parameters and receive a `job_id`.
- [ ] WebSocket events update status, terminal log, and pixel progress.
- [ ] Completed images render in the main canvas and session gallery.
- [ ] UI follows Matere desktop-first visual language without auth.
