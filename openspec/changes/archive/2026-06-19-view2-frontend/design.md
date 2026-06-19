# Design: View 2 Frontend Rebuild

## Technical Approach

Create a greenfield Next.js 16 App Router app in `/view2/` that replaces the retro `/view/` frontend with the `ai-studio-design-system` aesthetic. The architecture keeps business logic portable: port the API client, WebSocket handler, Zustand stores, and `useGenerationFlow` hook from `/view/`, then wrap them in a new 3-panel studio layout (chat sidebar + workspace canvas + assets drawer). All UI uses the design-system token file and base classes (`.btn`, `.input`, `.surface-panel`, `.text-mono`); component-scoped layout is handled by CSS Modules.

## Architecture Decisions

| Decision | Options | Tradeoffs | Choice |
|----------|---------|-----------|--------|
| App directory | `/view2/` greenfield vs refactor `/view/` | Greenfield lets `/view/` remain as rollback; refactor risks regressions. | Greenfield `/view2/`. |
| State library | Zustand vs Redux Toolkit vs React Context | Existing code uses Zustand; Redux adds boilerplate, Context causes render churn for frequent WS updates. | Zustand, split into `uiStore` and `generationStore`. |
| Styling strategy | Design-system CSS + CSS Modules vs Tailwind/shadcn | Spec forbids shadcn; Tailwind would duplicate tokens. | Copy `colors_and_type.css` into `/view2/src/styles/` and import via `globals.css`; CSS Modules only for layout geometry. |
| State machine representation | Discrete enum vs derived from latest event | Discrete enum is explicit and matches UI scenarios. | Frontend enum `Idle | Booting | DownloadingWeights | Generating | Done | Error`. |
| Reference asset handling | Base64 data URI vs object URL | Backend expects data URI for `image_base64`/`image_url`; data URI keeps existing API contract. | Keep FileReader → data URI in `AssetsDrawer`, store in `generationStore`. |
| WebSocket transport | Reuse `/view/` client vs new Socket.io | Backend exposes native WS; Socket.io adds dependency and mismatch. | Port `connectWebSocket` with exponential backoff (1s, 2s, 4s) and 3 retry limit. |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User submits prompt                          │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  InputBar ──► generationStore.setPrompt / setSelectedWorkflow        │
│  generate() via useGenerationFlow                                     │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  POST /api/generate ──► submitGenerate ──► startConnecting           │
│  WS /api/ws/generate/{job_id} ──► connectWebSocket                   │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  generationStore.addEvent maps event ► state machine transition      │
│  WorkspaceCanvas reads state/progress, renders result image          │
└─────────────────────────────────────────────────────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `/view2/package.json` | Create | Next.js 16, React 19, Zustand, lucide-react, Vitest, Testing Library, jsdom. |
| `/view2/next.config.ts` | Create | Reuse `/api/generate`, `/api/ws/generate/:jobId`, `/api/images/:jobId` rewrites pointing to Modal backend. |
| `/view2/vitest.config.ts` | Create | React plugin, `@/` alias, jsdom, `src/**/*.test.{ts,tsx}`. |
| `/view2/src/test/setup.ts` | Create | Mock `next/image`, import `@testing-library/jest-dom`. |
| `/view2/src/app/layout.tsx` | Create | Root layout, metadata, loads `globals.css`. |
| `/view2/src/app/page.tsx` | Create | Renders `GenerationStudio`. |
| `/view2/src/app/globals.css` | Create | `@import '../styles/colors_and_type.css'`; minimal reset. |
| `/view2/src/styles/colors_and_type.css` | Copy | Copy from `Design  reference/ai-studio-design-system/colors_and_type.css` — source of truth for tokens and base classes. |
| `/view2/src/features/generation/api/types.ts` | Create | Aligned `JobEvent` union: `booting_server \| downloading_weights \| generating \| progress \| completed \| error`; `GenerationState`, `WorkflowName`, etc. |
| `/view2/src/features/generation/api/client.ts` | Port/Create | `submitGenerate`, `getWsUrl`, `getImageUrl`, `connectWebSocket` with retry logic. |
| `/view2/src/features/generation/stores/generationStore.ts` | Port/Create | Prompt, parameters, currentJob, generationState, sessionHistory, reference assets, validation. |
| `/view2/src/features/generation/stores/uiStore.ts` | Create | `assetsDrawerOpen`, toggle/collapse actions. |
| `/view2/src/features/generation/hooks/useGenerationFlow.ts` | Port/Create | Orchestrates submit → WS → store updates; exposes view-model to components. |
| `/view2/src/features/generation/components/GenerationStudio.tsx` | Create | 3-panel root layout: `ChatSidebar`, `WorkspaceCanvas`, `AssetsDrawer`. |
| `/view2/src/features/generation/components/ChatSidebar.tsx` | Create | Message history + `InputBar` + `WorkflowSelector` + speed toggle. |
| `/view2/src/features/generation/components/InputBar.tsx` | Create | Textarea + send button; Enter to submit; empty prompt validation. |
| `/view2/src/features/generation/components/WorkflowSelector.tsx` | Create | Dropdown for `flux2_txt2img`, `flux2_editing`, `identidad_gguf`. |
| `/view2/src/features/generation/components/WorkspaceCanvas.tsx` | Create | Artboard placeholder, progress indicator, result image, error banner. |
| `/view2/src/features/generation/components/AssetsDrawer.tsx` | Create | Collapsible right panel for reference upload/gallery/remove. |
| `*.module.css` files | Create | Layout-only overrides (panel widths, flex behavior, canvas max bounds). |
| `*.test.tsx` / `*.test.ts` | Create | One test file per component/module using strict TDD. |

## Interfaces / Contracts

```ts
// Frontend state machine
export type GenerationState =
  | "idle"
  | "booting"
  | "downloadingWeights"
  | "generating"
  | "done"
  | "error";

// Backend-aligned event union
export type JobEventName =
  | "booting_server"
  | "downloading_weights"
  | "generating"
  | "progress"
  | "completed"
  | "error";

export interface JobEvent {
  event: JobEventName;
  job_id: string;
  timestamp: string;
  progress?: number | null;
  message?: string | null;
  result?: { image_path: string } | null;
  error?: { code: string; detail: string } | null;
}

export type WorkflowName =
  | "flux2_txt2img"
  | "flux2_editing"
  | "identidad_gguf";
```

State mapping from events:
- `booting_server` → `booting` (indeterminate)
- `downloading_weights` → `downloadingWeights` (indeterminate)
- `generating` / first `progress` → `generating` (determinate)
- `completed` → `done`
- `error` → `error`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit — store | `generationStore` transitions, validation, reference requirement | Vitest, direct store calls |
| Unit — hook | `useGenerationFlow` submit, WS event dispatch, cancel/reset | `@testing-library/react` with mocked `client.ts` |
| Unit — components | `InputBar`, `WorkflowSelector`, `AssetsDrawer`, `WorkspaceCanvas` render + interactions | `@testing-library/react`, jsdom, design-system class assertions |
| Integration — studio | Full prompt → generate → progress → result flow | Mock server + fake WebSocket |
| Build | Type checking & Next.js build | `tsc --noEmit` and `next build` |

Strict TDD rule: write the failing test (RED), implement the minimal code (GREEN), then refactor. No component file without a matching `.test.tsx`.

## Migration / Rollout

No migration required. `/view2/` is a parallel app; `/view/` remains untouched. Deploy behind a feature flag or separate route until verified, then switch the entry proxy. Delete `/view2/` if the rebuild fails — zero impact on the working system.

## Open Questions

- Should `/view2/` coexist temporarily under a sub-route (e.g., `/v2`) or fully replace `/view/` once verified?
- Do we need persisted chat history beyond the in-memory session? The current scope says no, but it affects `ChatSidebar` message list design.
