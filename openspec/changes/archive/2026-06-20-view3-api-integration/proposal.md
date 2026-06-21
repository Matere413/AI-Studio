# Proposal: View3 API Integration

## Intent

Connect the facade-only `view3/` Next.js studio to the live FastAPI/Modal generation API while preserving the existing I-Studio shell. The frontend must mirror the updated strict Pydantic v2 contract: workflow-discriminated requests, real booleans, forbidden legacy fields, terminal WS payload rules, and typed error envelopes.

## Scope

### In Scope
- Typed HTTP/WS clients for `POST /api/generate`, `WS /ws/generate/{job_id}`, and proxied image loading.
- `workflow_name`-discriminated TS DTOs for `flux2_txt2img`, `flux2_editing`, and `identidad_gguf`.
- Chat send flow, workflow selector, strict `use_turbo` mapping, live status/progress, typed errors, and Studio Canvas image display.

### Out of Scope
- Assets upload/router work beyond graceful empty/no-op states.
- New state libraries; use lean hooks/reducer first.
- Multi-job queueing or workflow UX redesign beyond the selector replacement.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `generative-ai-studio-frontend`: replace facade-only behavior with live API/WS integration; Workflow Selector replaces Aspect Ratio; add Retry after WS exhaustion.
- `image-generation`: frontend must consume strict response, terminal event, closed error-code, and `/images/{job_id}` envelopes.
- `flux2-workflows`: enforce `use_turbo` as a real boolean only for Flux 2 workflows and require `image_base64` only for editing.
- `identity-gguf-workflows`: require `image_url`, allow only `http(s)` or `data:` URI, scope dimensions/seed to identity only.

## Approach

Use a dependency-light hexagonal slice: shared fetch/error normalization, feature DTOs, pure `buildGenerateRequest`, WS hook with 3 retries (1s/2s/4s) and a user-visible Retry button. Route generated images through a Next.js proxy (`app/api/images/[jobId]/route.ts`) to hide Modal URLs and prepare for auth/CORS constraints.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `view3/src/shared/infrastructure/` | New | Fetch, env, error-envelope parsing |
| `view3/src/features/chat/` | Modified | DTOs, request factory, composer, messages, WS lifecycle |
| `view3/src/features/studio/` | Modified | Job events, canvas image/status, error labels |
| `view3/src/app/api/images/[jobId]/route.ts` | New | Next.js image proxy |
| `view3/src/app/page.tsx` | Modified | Replace mock imports with application state |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DTO drift from Pydantic models | Med | Mirror literal unions; contract tests for request bodies/envelopes |
| Modal WS/CORS issues | Med | Proxy images; test WS handshake and reconnect behavior |
| Cold starts feel broken | Med | Render `booting_server`/`downloading_weights` messages honestly |

## Rollback Plan

Revert the `view3-api-integration` files to mock-data imports and remove the image proxy/env wiring; backend remains untouched.

## Dependencies

- Backend `api/src/features/generation/models.py` and router contract.
- `NEXT_PUBLIC_API_BASE_URL` / WS derivation for Modal dev endpoint.

## Success Criteria

- [ ] Valid prompts submit strict JSON with no legacy fields or coerced booleans.
- [ ] WS updates drive chat/status/canvas through completed/error terminal states.
- [ ] Workflow Selector replaces Aspect Ratio and Retry appears after 3 failed reconnects.
