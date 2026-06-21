# Design: View3 API Integration

## Technical Approach

Wire the Next.js 14 studio shell to the live FastAPI/Modal backend by incrementally filling hexagonal slices with domain DTOs, application hooks, and infrastructure clients — replacing mock imports with typed API/WS flows. No new dependencies.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| State management | `useReducer` (only) | `useReducer` in `page.tsx` | Proposal mandates "lean hooks/reducer first"; no external state library. Reducer handles `selectedWorkflow`, `currentJob`, `generationState`, messages, and error — sufficient for single-page studio. |
| API client location | `view3/src/lib/api.ts` vs `shared/infrastructure/` | `shared/infrastructure/api-client.ts` | Follows project's hexagonal convention; `@/` alias provides the same ergonomics. Re-export barrel satisfies spec's `lib/api.ts` contract. |
| WS client | `useWebSocket` generic vs job-specific hook | `useGenerationJob(jobId)` with embedded `wsReducer` | Job-scoped reducer owns retry counter, backoff timers, and terminal state detection. No reusable WS abstraction needed for three workflows. |
| Image proxy | Middleware vs Route Handler | App Router `route.ts` — `GET /api/images/[jobId]` | Standard Next.js 14 pattern. Streams binary with upstream `Content-Type` via `fetch`; no middleware complexity. |

## Data Flow

```
ChatComposer                    [POST /api/generate]
  │  buildGenerateRequest()           │
  ├──► submitGenerate(dto) ──────────►│──► { job_id, status: "pending" }
  │                                   │
  │  useGenerationJob(job_id)         │
  ├──► new WebSocket(wsUrl) ─────────►│──► JobEvent stream
  │     reducer: CONNECTED →          │     progress/message → ChatSidebar
  │     PROGRESS / COMPLETED / ERROR  │     completed.result → StudioCanvas
  │     retry x3 (1s/2s/4s)          │
  │                                   │
  │  StudioCanvas                     │
  └──► GET /api/images/{jobId} ──────►│──► binary image
         (Next.js proxy)              │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `view3/src/shared/infrastructure/api-client.ts` | **Create** | `submitGenerate(dto)`, `getWsUrl(jobId)`, `fetchImageBinary(jobId)`, `normalizeError(response)` |
| `view3/src/shared/infrastructure/env.ts` | **Create** | Reads `NEXT_PUBLIC_API_BASE_URL`; derives WS URL (`wss://` from `https://`) |
| `view3/src/shared/infrastructure/index.ts` | **Create** | Barrel |
| `view3/src/features/chat/domain/dto.ts` | **Create** | `WorkflowName`, discriminated `GenerateRequest` types, `validateRequest()` |
| `view3/src/features/chat/application/build-generate-request.ts` | **Create** | Pure function: `(prompt, workflow, params) → GenerateRequest` |
| `view3/src/features/chat/application/use-generation-job.ts` | **Create** | `useReducer`-based WS hook: connects, dispatches events, retries 3× (1s/2s/4s), exposes `retry()` |
| `view3/src/features/studio/domain/dto.ts` | **Create** | `GenerateResponse`, `JobEvent`, `JobEventResult`, `JobEventError` |
| `view3/src/features/chat/domain/index.ts` | **Modify** | Re-export DTOs |
| `view3/src/features/chat/application/index.ts` | **Modify** | Re-export hooks |
| `view3/src/features/chat/infrastructure/index.ts` | **Modify** | Re-export shared infrastructure |
| `view3/src/features/studio/domain/index.ts` | **Modify** | Re-export studio DTOs |
| `view3/src/features/chat/presentation/components/ChatComposer.tsx` | **Modify** | Replace Aspect Ratio `PillSelect` with Workflow Selector; wire `onSend` to `submitGenerate` |
| `view3/src/features/chat/presentation/components/MessageList.tsx` | **Modify** | Accept real `Message[]` + job event cards (replaces `MockMessage`) |
| `view3/src/features/chat/presentation/components/ChatSidebar.tsx` | **Modify** | Pass live state instead of `MOCK_MESSAGES` |
| `view3/src/features/studio/presentation/components/StudioCanvas.tsx` | **Modify** | Render result image via `/api/images/{jobId}`; show event status text |
| `view3/src/features/studio/presentation/components/StatusBar.tsx` | **Modify** | Accept `status` + `progress` props; show `booting_server` / `downloading_weights` / `generating` with progress % |
| `view3/src/app/api/images/[jobId]/route.ts` | **Create** | Proxies `GET {API_BASE_URL}/images/{jobId}` → streams binary with upstream `Content-Type`; 404 → `{ code, detail }` |
| `view3/src/app/page.tsx` | **Modify** | Add `useReducer` for `StudioState`; remove `MOCK_MESSAGES`/`MOCK_ASSETS` imports; wire hooks to children |

## Interfaces / Contracts

```typescript
// shared/infrastructure/api-client.ts
function submitGenerate(req: GenerateRequest): Promise<GenerateResponse | ApiError>;
function getWsUrl(jobId: string): string;
function normalizeError(status: number, body: unknown): ApiError;

// features/chat/application/use-generation-job.ts
function useGenerationJob(jobId: string | null): {
  events: JobEvent[];
  state: "connecting" | "streaming" | "completed" | "error" | "exhausted";
  progress: number;
  retryCount: number;
  retry: () => void;
};

// features/chat/application/build-generate-request.ts
function buildGenerateRequest(
  prompt: string,
  workflow: WorkflowName,
  params: Partial<GenerateRequest>
): GenerateRequest;
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `buildGenerateRequest` — correct field inclusion/exclusion per workflow | Pure function, no mocks needed |
| Unit | `normalizeError` — 422, 400, 500, unknown shapes | Table-driven; each HTTP status + body |
| Integration | `useGenerationJob` — WS connect, event dispatch, retry exhaustion | Mock WebSocket; assert state transitions |
| Integration | Image proxy route — 200 (streams), 404 (error JSON) | Mock `fetch`; test `route.ts` handler |
| E2E | Full send → WS stream → canvas render | Playwright; against local backend or recorded fixtures |

## Migration / Rollout

No migration required. The change replaces mock-only components with live ones. Rollback: revert `page.tsx` to import `MOCK_MESSAGES`/`MOCK_ASSETS` and remove `api/` route.

## Open Questions

- [ ] Backend WS endpoint not yet deployed — contract tests need mock server or recorded fixtures until available.
