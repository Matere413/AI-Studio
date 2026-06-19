# Proposal: View 2 Frontend Rebuild

## Intent

The existing `/view/` frontend was built on a retro pixel-art design system (CRT effects, VT323, chunky borders) that contradicts the product's required serious, minimalist, DaVinci Resolve-like aesthetic. Rebuild as a greenfield Next.js App Router app in `/view2/` using the canonical `ai-studio-design-system`.

## Scope

### In Scope
- Greenfield `/view2/` Next.js 16 App Router app with `ai-studio-design-system` CSS tokens
- 3-panel layout: chat sidebar (left) + workspace canvas (center) + assets drawer (right, collapsible)
- Chat sidebar: prompt input bar at bottom, manual "Workflow" dropdown + speed selector
- Workspace canvas: generated images displayed as working artboard
- Assets drawer: reference image/mask upload and management
- Port business logic: Zustand store, `useGenerationFlow` hook, API client
- Align frontend event types with backend (`booting_server | downloading_weights | generating | progress | completed | error`)

### Out of Scope
- Orchestrator agent integration (manual workflow selector is the interim solution)
- Mobile/responsive layouts (desktop-first studio tool)
- New backend endpoints or workflow types
- shadcn/ui (conflicts with custom design system)

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `generative-ai-studio-frontend`: Complete layout/design/interaction overhaul — replaces 340px sidebar + terminal overlay with 3-panel chat-centric layout; replaces retro pixel-art tokens with `ai-studio-design-system`; adds manual workflow dropdown; moves reference uploads to dedicated assets drawer

## Approach

Import `colors_and_type.css` directly into `globals.css` as the design foundation. Rebuild all UI components using design-system classes (`.btn`, `.input`, `.surface-panel`, `.text-mono`). Port decoupled business logic (API client, Zustand store, WebSocket hook) from `/view/` with event-type alignment. Use `lucide-react` (strokeWidth 1.5) for icons.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `/view2/` | New | Greenfield Next.js App Router root |
| `/view2/src/app/` | New | Layout, page, globals.css with design tokens |
| `/view2/src/features/generation/` | New | Rebuilt components + ported stores/hooks |
| `/view2/src/lib/api.ts` | New | Ported API client with event-type alignment |
| `/view2/src/components/` | New | ChatSidebar, WorkspaceCanvas, AssetsDrawer |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Event type mismatch with backend | High | Map full backend event enum in types before building UI |
| Design system CSS leakage | Low | Isolated `/view2/` directory, no shared globals |
| Workflow selector UX unclear without orchestrator | Med | Simple dropdown with known workflow IDs from backend |

## Rollback Plan

`/view2/` is a parallel directory. The existing `/view/` remains untouched. If the rebuild fails, delete `/view2/` — zero impact on working system.

## Dependencies

- `Design reference/ai-studio-design-system/colors_and_type.css` — design tokens
- FastAPI backend API contract (`POST /generate`, `WS /ws/generate/{job_id}`, `GET /images/{job_id}`)
- `lucide-react` — icon library

## Success Criteria

- [ ] 3-panel layout renders with correct design-system tokens (dark surfaces, amber accents, geometric sans)
- [ ] Chat sidebar submits prompts via existing `/api/generate` endpoint
- [ ] Manual workflow dropdown selects between `flux2_txt2img`, `flux2_editing`, `identidad_gguf`
- [ ] WebSocket progress streaming works with full backend event spectrum
- [ ] Assets drawer uploads and manages reference images
- [ ] No retro pixel-art visual residue
