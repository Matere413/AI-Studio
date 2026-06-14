# Design: Generative AI Studio Frontend

## Technical Approach

Replace the starter App Router page with a client-side studio shell under `view/src/components/studio/`, styled with existing Matere globals (`colors_and_type.css`, `portfolio.css`) plus scoped CSS Modules for layout-specific rules. The page will submit `POST /api/generate`, connect to `/api/ws/generate/{job_id}`, and drive all UI from a small Zustand store. This satisfies the layout, state machine, WebSocket retry, cold-start, validation, gallery, and API requirements.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| CSS Modules for studio components | Avoids global class collisions while still using Matere tokens/utilities | Use `*.module.css`; keep existing globals as design primitives |
| Zustand over Context/reducer | Adds one dependency, but keeps async WebSocket events and history updates simple | Use `useGenerationStore` with synchronous mutations and no persistence |
| Relative `/api/*` integration via rewrites | Great local DX; production WebSocket hosting still needs validation | Use Next.js rewrites to FastAPI, with env-driven backend origin |

## Data Flow

```text
StudioPage
  └─ StudioLayout
     ├─ Sidebar ── validate/set inputs ──→ useGenerationStore
     ├─ Canvas ── currentJob/result ─────→ image preview/status
     ├─ TerminalLog ── currentJob.events ─→ collapsible VT323 log
     └─ ImageGallery ── sessionHistory ───→ newest-first thumbnails

Generate click → submitGenerate() → POST /api/generate → job_id
job_id → WebSocket /api/ws/generate/{job_id} → JobEvent → store → UI
completed.result.image_path → sessionHistory prepend → currentJob reset
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `view/src/app/layout.tsx` | Modify | Remove `next/font/google`; rely on local `@font-face`; update metadata. |
| `view/src/app/page.tsx` | Modify | Render `StudioLayout` instead of starter content. |
| `view/src/app/page.module.css` | Modify | Replace starter styles or reduce to page wrapper. |
| `view/src/components/studio/StudioLayout.tsx` | Create | Desktop grid: 340px sidebar + flexible canvas; stacks below 1024px. |
| `view/src/components/studio/Sidebar.tsx` | Create | Prompt, workflow params, validation errors, Generate/Cancel controls. |
| `view/src/components/studio/Canvas.tsx` | Create | Status badge, output placeholder/image, progress area. |
| `view/src/components/studio/TerminalLog.tsx` | Create | Collapsible CRT terminal using `VT323` and WebSocket messages. |
| `view/src/components/studio/PixelProgressBar.tsx` | Create | Indeterminate cold-start state, determinate striped pixel fill. |
| `view/src/components/studio/ImageGallery.tsx` | Create | Client-only completed session thumbnails, newest first. |
| `view/src/components/studio/*.module.css` | Create | Chunky borders, hard shadows, Matere 4px spacing, responsive layout. |
| `view/src/stores/generationStore.ts` | Create | Zustand input, job, events, state machine, history contract. |
| `view/src/lib/api.ts` | Create | `submitGenerate`, `getWsUrl`, WebSocket retry helper or URL builder. |
| `view/next.config.ts` | Modify | Add external rewrites for `/api/:path*`. |
| `view/package.json` | Modify | Add `zustand`. |

## Interfaces / Contracts

```ts
type GenerationState = "idle" | "connecting" | "generating" | "done" | "error";
type WorkflowName = "txt2img" | "img2img" | "controlnet";

interface GenerationParameters {
  workflow_name: WorkflowName;
  checkpoint_url?: string;
  lora_url?: string;
}

interface JobEvent {
  event: "pending" | "running" | "completed" | "error";
  job_id: string;
  timestamp: string;
  progress?: number | null;
  message?: string | null;
  result?: { image_path: string } | null;
  error?: { code: string; detail: string } | null;
}

interface CurrentJob {
  job_id: string;
  status: JobEvent["event"] | "connecting";
  progress: number | null;
  events: JobEvent[];
  errorMessage?: string;
}

interface HistoryItem {
  id: string;
  imagePath: string;
  prompt: string;
  parameters: GenerationParameters;
  completedAt: string;
}

interface GenerationStore {
  prompt: string;
  parameters: GenerationParameters;
  currentJob: CurrentJob | null;
  generationState: GenerationState;
  sessionHistory: HistoryItem[];
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  startConnecting(jobId: string): void;
  addEvent(event: JobEvent): void;
  fail(message: string): void;
  cancel(): void;
  reset(): void;
}
```

`submitGenerate(prompt, params)` posts `{ prompt, ...params }` to `/api/generate` and returns `{ job_id, status: "pending" }`. `getWsUrl(jobId)` returns `/api/ws/generate/${jobId}` for the browser.

`next.config.ts` will use:

```ts
const apiOrigin = process.env.FASTAPI_ORIGIN ?? "http://localhost:8000";
async rewrites() {
  return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Store transitions, validation, history ordering | Vitest/Jest if added; otherwise isolate pure helpers for later runner setup. |
| Integration | `submitGenerate`, `getWsUrl`, WebSocket retry exhaustion | Mock `fetch` and `WebSocket`; verify 1s/2s/4s retry behavior. |
| E2E | User submits, sees progress/log, result/gallery | Manual MVP pass or Playwright when frontend test stack is added. |

## Migration / Rollout

No data migration required. Roll out as a frontend-only MVP; backend contract remains unchanged. Rewrites are configured by `FASTAPI_ORIGIN` and default to local FastAPI.

## Open Questions

- [ ] Confirm deployed frontend host supports WebSocket rewrites; if not, production should use direct FastAPI `wss://` with CORS/origin configuration.
