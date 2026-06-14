# Exploration: Generative AI Studio Frontend MVP

## Current State

The backend is a production-ready FastAPI application running on Modal with GPU (T4) scale-to-zero. It exposes `POST /generate` (202 Accepted → `job_id`) and `WS /ws/generate/{job_id}` (streams `JobEvent` JSON with `event`, `progress`, `message`, `result`). Job state is persisted via `modal.Dict` so WebSocket reconnects resume correctly.

The frontend (`view/`) is a freshly initialized Next.js 16.2.9 App Router project with React 19. The Matere design system CSS (`colors_and_type.css`) is already imported in `globals.css` and provides a complete token set: earth-tone palette, pixel fonts (Silkscreen, Pixelify Sans, VT323), hard-offset shadows, chunky borders, and CRT/scanline utilities. A design reference prototype (`Design reference/ai-studio-app.html`) already sketches a studio layout: top nav, 340px sidebar for controls, and a main canvas for the image preview.

Dependencies are minimal: only `next`, `react`, `react-dom`. No state management, data fetching, or UI component libraries are installed yet.

## Affected Areas

- `view/src/app/layout.tsx` — must swap Google Fonts for local Matere fonts (Silkscreen, Pixelify Sans, VT323, Geist). The current `Geist` + `Geist_Mono` imports from `next/font/google` conflict with the local design system.
- `view/src/app/page.tsx` — currently the Next.js starter page; must be replaced by the studio layout.
- `view/src/app/globals.css` — already imports the design system; minor Next.js overrides are fine.
- `view/next.config.ts` — needs proxy/rewrite rules for backend integration.
- `view/package.json` — needs additional runtime dependencies for state management and WebSocket handling.
- `api/app.py` (or backend config) — may need CORS headers if direct cross-origin is chosen.
- `openspec/changes/generative-ai-studio-frontend/exploration.md` — this file.

## Approaches

### 1. Layout & UX

#### Option A: Sidebar (340px) + Main Canvas (flexible) — Single-Page Studio
- **Description**: Adopt the existing design reference almost verbatim. Left sidebar holds prompt textarea, model parameters (steps, CFG, seed, width/height), and a chunky "Generate" button. Main canvas shows a status toolbar (badge + timer), a large image preview container with a hover overlay (dimensions/seed), and a bottom gallery strip for recent generations.
- **Pros**: Matches the Matere prototype exactly. Minimal decision fatigue. Users familiar with ComfyUI/Stable Diffusion UIs will feel at home. The 340px sidebar is wide enough for comfortable parameter editing without crowding.
- **Cons**: Mobile requires a separate breakpoint strategy (sidebar could become a bottom sheet or collapse). Gallery in the same view might crowd the canvas on small screens.
- **Effort**: Low

#### Option B: Drawer/Overlay Controls + Full-Canvas Focus
- **Description**: The main canvas takes 100% of the viewport. Controls live in a slide-out drawer (triggered by a pixel-art hamburger icon) or modal overlays. The image is always the hero. Parameters appear only when needed.
- **Pros**: Maximum screen real estate for the image. Very "immersive".
- **Cons**: Hiding controls makes iterative tuning slower — users will toggle the drawer constantly. Harder to implement the chunky Matere borders without the sidebar providing natural visual separation.
- **Effort**: Medium

#### Option C: Three-Pane (Sidebar + Canvas + Right Inspector)
- **Description**: Add a third pane on the right for metadata, history, or a node-graph view of the workflow.
- **Pros**: Future-proof for advanced features.
- **Cons**: Overkill for an MVP. The Matere aesthetic works best with strong, simple shapes; three panes risk visual fragmentation.
- **Effort**: High

### 2. Real-Time Feedback (WebSocket Progress)

#### Option A: Retro Terminal Log (VT323) + Chunky Progress Bar
- **Description**: A small panel at the bottom of the sidebar (or below the canvas) shows a scrolling log of WebSocket messages in `VT323` font (e.g., `[14:32:01] Job queued...`, `[14:32:05] Running step 3/30...`). Above the log, a pixel progress bar (from the design system preview `18-progress.html`) fills with a striped pattern. The `status-badge` in the toolbar updates color (sage → ember) and text.
- **Pros**: Perfectly fits the Matere aesthetic — the VT323 font is literally included for this purpose. The log provides transparency and debugging value. The progress bar gives immediate visual feedback. The existing design system already has `.cursor` blink animation and `.crt` scanlines.
- **Cons**: The log can grow long; needs a max-height with overflow scroll. Slightly more DOM nodes than a single progress bar.
- **Effort**: Low

#### Option B: Minimal Status Badge + Toast Notifications
- **Description**: Only update the toolbar `status-badge` (e.g., `MODAL: RUNNING`). When the job completes, show a chunky toast (from `19-overlays.html`) with the result.
- **Pros**: Minimal UI noise. Easy to implement.
- **Cons**: Users have no sense of progress during long GPU inference. The Matere aesthetic is "chunky and informative" — a single badge feels too thin.
- **Effort**: Low

#### Option C: Node-Graph Animation Overlay
- **Description**: A pixel-art animation on the canvas (e.g., a small spinning pixel gear or a "rendering..." sprite) while the job runs.
- **Pros**: Visually engaging.
- **Cons**: Distracting. Harder to implement than a log. No tangible progress information.
- **Effort**: Medium

### 3. State Management

#### Option A: React Context + useReducer + Native WebSocket
- **Description**: A single `StudioContext` provider at the app root holds `generationState` (prompt, params, currentJob, history) and `websocketStatus` (connected, messages). A `useReducer` handles actions: `START_JOB`, `RECEIVE_EVENT`, `COMPLETE_JOB`, `ADD_TO_HISTORY`. The WebSocket connection is managed inside a `useEffect` hook in a provider or a dedicated component.
- **Pros**: Zero extra dependencies. Fits the "minimal MVP" philosophy. No bundle size increase. React 19's improved concurrent features make Context more performant for this scale.
- **Cons**: Boilerplate scales poorly if the app grows beyond 3-4 features. Async logic (WebSocket reconnect, error handling) inside hooks can get messy.
- **Effort**: Low

#### Option B: Zustand + Native WebSocket
- **Description**: Zustand store for the generation and history state. A small `useGenerationStore` with slices for `params`, `job`, `history`, `connection`. The WebSocket logic lives in a separate module that calls `store.getState().addEvent()`.
- **Pros**: Very lightweight (~1KB). Excellent for async state. No provider boilerplate. Easy to add persistence later (e.g., `zustand/middleware` for localStorage).
- **Cons**: One extra dependency. For a single-page MVP, the DX gain over Context is marginal.
- **Effort**: Low

#### Option C: TanStack Query + Zustand (Hybrid)
- **Description**: TanStack Query (`@tanstack/react-query`) handles the server state: `POST /generate` mutation, WebSocket events via a custom `useWebSocket` hook that updates the query cache. Zustand handles purely client-side UI state (sidebar open/closed, selected history index).
- **Pros**: The "correct" architecture for production. TanStack Query gives caching, retries, deduping, and optimistic updates for free.
- **Cons**: Overkill for an MVP. Adds ~12KB gzipped. The WebSocket events are not traditional REST fetches, so the value of TanStack Query is diminished unless we also add polling fallbacks.
- **Effort**: Medium

### 4. Integration (Next.js ↔ FastAPI Backend)

#### Option A: Next.js Rewrites (Proxy)
- **Description**: Configure `next.config.ts` with `rewrites` so that `/api/generate` and `/api/ws/generate/:job_id` are proxied to the Modal backend URL. The frontend code calls relative paths. The browser thinks it is talking to the same origin.
- **Pros**: No CORS configuration needed on the backend. No preflight overhead. WebSocket upgrades work seamlessly through the proxy. Works in both dev and production (if deployed on the same domain).
- **Cons**: The Modal backend URL must be known at build time (or via env var). If the frontend and backend are on different domains in production, this requires a Vercel/Next.js server to always act as the proxy, which means the Next.js server must handle WebSocket upgrades — this works in dev but can be tricky on serverless deployments (Vercel Edge does not support long-lived WebSocket connections).
- **Effort**: Low

#### Option B: Direct Cross-Origin with CORS Headers
- **Description**: The frontend calls `https://{modal-url}/generate` and `wss://{modal-url}/ws/generate/{job_id}` directly. The FastAPI backend adds CORS middleware (`CORSMiddleware` from `fastapi.middleware.cors`) allowing the frontend origin.
- **Pros**: Clean separation of concerns. No Next.js server bottleneck. The Modal backend can scale independently. Works regardless of where the frontend is hosted.
- **Cons**: Requires configuring CORS on the FastAPI app. WebSocket connections to cross-origin servers work fine in modern browsers, but some corporate firewalls might block `wss://` on non-standard ports. The Modal URL is exposed to the client (acceptable for a studio, but means the backend URL is public).
- **Effort**: Low

#### Option C: Next.js API Routes (Server-Side Middleware)
- **Description**: Create `app/api/generate/route.ts` and `app/api/ws/generate/route.ts` in Next.js. These serverless functions forward the request to the backend. For WebSockets, this is not possible in standard Next.js API routes (they are request/response, not long-lived). Would require a separate WebSocket server or use Server-Sent Events (SSE) instead.
- **Pros**: Backend URL is never exposed to the client. Good for API key management if you need to add auth later.
- **Cons**: Next.js App Router API routes do not support WebSocket upgrades. You would need to change the backend protocol from WebSocket to Server-Sent Events (SSE) or maintain a separate WebSocket proxy. This is architectural friction for an MVP.
- **Effort**: High

## Recommendation

1. **Layout**: **Option A (Sidebar + Main Canvas)**. It already has a design prototype. It is the most intuitive for a generation studio. The 340px sidebar is a perfect width for the Matere chunky controls.

2. **Real-Time Feedback**: **Option A (Terminal Log + Chunky Progress Bar)**. The Matere design system explicitly includes `VT323` for terminal aesthetics, `.cursor` for blinking cursors, and `18-progress.html` for pixel progress bars. This is the most authentic expression of the brand. Place the progress bar in the sidebar above the "Generate" button, and the terminal log in a collapsible panel below the canvas or at the bottom of the sidebar.

3. **State Management**: **Option B (Zustand)**. While React Context is viable, the MVP will likely grow (history, multiple workflows, editing). Zustand gives us async-friendly state for ~1KB and avoids the "provider pyramid" problem. It is the pragmatic choice for a studio app that will handle WebSocket events.

4. **Integration**: **Option A (Next.js Rewrites) for local development**, and **Option B (Direct with CORS) for production deployment**. The best hybrid: use `next.config.ts` rewrites so that `npm run dev` works seamlessly without CORS headaches. In production, add `CORSMiddleware` to the FastAPI app and have the frontend connect directly to the Modal URL. This gives us the best local DX and the best production scalability.

**Implementation Plan (MVP slice)**:
- `layout.tsx`: Remove Google Font imports, rely on local `@font-face` declarations from the design system (already in `colors_and_type.css`). Update `<title>` and metadata.
- `page.tsx`: Build the studio layout component. Use CSS Grid/Flexbox with the design system tokens.
- `next.config.ts`: Add `rewrites` for `/api/generate` and `/api/ws/generate/:job_id`.
- `api/app.py`: Add `CORSMiddleware` as a production fallback.
- New files in `view/src/`:
  - `components/studio/StudioLayout.tsx`
  - `components/studio/Sidebar.tsx`
  - `components/studio/Canvas.tsx`
  - `components/studio/TerminalLog.tsx`
  - `components/studio/PixelProgressBar.tsx`
  - `hooks/useGeneration.ts` (WebSocket + Zustand logic)
  - `stores/generationStore.ts` (Zustand store)
  - `lib/api.ts` (fetch wrapper for POST /generate)

## Risks

- **WebSocket on Serverless**: If the frontend is deployed to Vercel, the Next.js dev proxy (rewrites) works locally, but Vercel Edge does not support long-lived WebSocket connections. The production recommendation (direct CORS) mitigates this, but the team must be aware that the `next.config.ts` rewrites are for dev convenience only.
- **Font Loading**: The Matere fonts are in `public/fonts/`. If they are not preloaded, the chunky pixel text will FOUT (flash of unstyled text), which is especially ugly with monospace fallbacks. Add `<link rel="preload">` tags in `layout.tsx`.
- **React 19 + Next.js 16 Compatibility**: The project uses Next.js 16.2.9 and React 19.2.4. These are very recent. Some third-party libraries (e.g., TanStack Query v4) might not be fully compatible. If we add dependencies later, we must verify React 19 compatibility.
- **Modal Cold Start**: The first WebSocket event after a cold start might take 30-60 seconds. The UI must handle this gracefully (the terminal log should show "Warming up GPU..." and the progress bar should be in an indeterminate/pulsing state, not stuck at 0%).
- **Mobile UX**: The 340px sidebar is not responsive. The MVP should at least include a `@media (max-width: 768px)` rule that stacks the sidebar above the canvas or turns it into a collapsible drawer.
- **Job History Persistence**: The current backend spec says `modal.Dict` is the store. If the Modal app is redeployed, the dict might be reset. The frontend should not rely on the backend for long-term history; the Zustand store should persist to `localStorage` so the user's session history survives page refreshes.

## Ready for Proposal

**Yes.** The exploration is complete enough to write a proposal. The orchestrator should tell the user:

> "We are ready to build the MVP frontend. The exploration confirms the design reference prototype (`ai-studio-app.html`) is the right starting point for the layout. The UI will use a **340px sidebar for controls** (prompt, parameters, generate button) and a **main canvas for the image preview** with a **retro terminal log** and **pixel progress bar** for real-time feedback. State will be managed with **Zustand** (lightweight, async-friendly). Integration will use **Next.js rewrites in dev** and **direct CORS in production**.
>
> The key open question is: **Should the MVP include a responsive/mobile breakpoint, or is desktop-only acceptable for the first slice?** The prototype is desktop-only."
