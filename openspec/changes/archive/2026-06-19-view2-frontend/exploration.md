## Exploration: view2-frontend

### Current State
The project has a working FastAPI backend (`api/`) that orchestrates ComfyUI JSON workflows via Modal. It exposes three endpoints consumed by the frontend:
- `POST /generate` — submits a generation job (prompt + workflow parameters).
- `GET /images/{job_id}` — serves the resulting image.
- `WS /ws/generate/{job_id}` — streams job lifecycle events (`booting_server`, `downloading_weights`, `generating`, `progress`, `completed`, `error`).

The existing `/view/` is a Next.js 16 App Router app (React 19, Zustand, Vitest). It contains functional API integration, a Zustand generation store, and a `useGenerationFlow` hook. **However, it was built on the wrong design system**: a retro pixel-art / burnt-sunset aesthetic (pixel fonts like Silkscreen and VT323, chunky borders, CRT effects) that contradicts the product’s required serious, minimalist, DaVinci Resolve-like tool interface.

The canonical design system lives in `Design reference/ai-studio-design-system/` and defines:
- Dark high-contrast surfaces (`#1c1917` background, `#292524` panels).
- Geometric sans-serif + monospace typography.
- Amber (`#d97706`) / gold (`#eab208`) accents.
- 4px spacing grid, 1px borders instead of shadows, pill-shaped buttons (`radius: 100px`).
- A conversational, agent-first layout: **left sidebar (chat)**, **central borderless Studio/Workspace canvas**, **collapsible right assets menu**.

### Affected Areas
- `/view2/` — new greenfield Next.js App Router root directory.
- `/view2/src/app/globals.css` — must import the design system CSS tokens.
- `/view2/src/app/layout.tsx` — root shell with dark theme and correct metadata.
- `/view2/src/app/page.tsx` — main page composing Sidebar + Workspace + AssetsDrawer.
- `/view2/src/lib/api.ts` — can be ported from `/view/src/lib/api.ts` but needs event-type alignment with backend.
- `/view2/src/features/generation/stores/generationStore.ts` — logic reusable, styling removed.
- `/view2/src/features/generation/hooks/useGenerationFlow.ts` — logic reusable, no style coupling.
- `/view2/src/features/generation/components/*` — every UI component must be rebuilt using design-system classes (`.btn`, `.input`, `.surface-panel`, `.text-mono`, `.text-caps`).

### Approaches

1. **Greenfield `/view2/` using the provided `colors_and_type.css` as global foundation**
   - Pros: The design system already ships a complete, working CSS file with tokens, base component classes (`.btn`, `.btn-primary`, `.input`, `.surface-panel`), and keyframe animations. Porting logic from `/view/` is straightforward because the retro styles were mostly in CSS Modules, not intertwined with business logic.
   - Cons: Global CSS is less scoped than CSS Modules; we must ensure no leakage (mitigated by app-level isolation in `/view2/`).
   - Effort: **Medium**

2. **Greenfield `/view2/` with Tailwind CSS mapping all design tokens**
   - Pros: Aligns with modern Next.js conventions, utility-first maintainability.
   - Cons: Requires manually translating ~50 CSS variables and component classes into `tailwind.config.ts`; adds build-step complexity for what is already a finished CSS spec.
   - Effort: **Medium-High**

3. **Fork existing `/view/` and restyle in-place**
   - Pros: Reuses working API integration and component structure.
   - Cons: The retro design system is deeply baked into global styles (`globals.css`, `colors_and_type.css`, `portfolio.css`) and CSS Modules. Extracting it is error-prone and the user explicitly wants a greenfield rebuild because the original approach “didn’t work out.”
   - Effort: **Medium** (but high risk of visual residue)

### Recommendation
**Adopt Approach 1**: create `/view2/` as a fresh Next.js App Router app, import `colors_and_type.css` directly into `globals.css`, and rebuild components as clean React components using the design-system CSS classes.

Reasoning:
- The design system CSS is **production-ready** and defines every token and base component we need.
- The business logic in `/view/` (API client, Zustand store, WebSocket hook) is **decoupled from styling** and can be ported with minimal changes.
- A greenfield directory eliminates any risk of retro-pixel style leakage.
- The UI kit (`ui_kits/app/`) provides a concrete React reference for the desired layout (Sidebar, OrchestratorArea, InputBar, MessageBubble, GalleryItem).

### Risks
- **Event type mismatch**: The backend emits `booting_server | downloading_weights | generating | progress | completed | error`, while the frontend’s `JobEvent` type currently only knows `pending | running | completed | error`. The new frontend must handle the full backend event spectrum.
- **Icon strategy**: The design system forbids emojis and requires thin geometric line icons (1–1.5px stroke). The UI kit uses inline SVGs; we should continue that pattern or adopt a lightweight, customizable icon set (e.g., `lucide-react` with `strokeWidth={1.5}`) and verify it matches the aesthetic.
- **Image upload in chat paradigm**: The original UI had dedicated `IdentitySettingsPanel` and `PromptPanel` components. The new design shifts these into a chat-centric sidebar with quick technical overrides (Speed, Format). We need to design how reference-image upload and workflow selection surface inside the chat input bar.
- **No shadcn/ui base**: The design system is custom, not derived from shadcn. We should not introduce shadcn unless the user explicitly requests it, because its default tokens and radii would fight the custom spec.
- **Backend API scope**: Currently only `generation_router` is mounted in `api/app.py`. The design system mentions editing and ControlNet workflows; if those routers are added later, the frontend layout must accommodate them without structural changes.

### Ready for Proposal
**Yes.** We have a clear understanding of the backend contract, the design system tokens, the canonical layout, and the scope of reusable logic. The next recommended phase is **sdd-propose**.
