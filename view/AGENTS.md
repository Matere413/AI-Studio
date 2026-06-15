<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Frontend Architecture Conventions

Use a feature-first structure for domain code and keep `src/app/` thin.

| Area | Convention |
|------|------------|
| Generation feature | Put generation-specific API clients, types, hooks, stores, components, CSS modules, and tests under `src/features/generation/`. |
| Shared UI | Put reusable, domain-agnostic UI primitives under `src/shared/components/ui/`. |
| App routes | Keep route files focused on composition and import feature entry components instead of owning feature logic. |
| Global styles | Keep global design-system CSS under `src/styles/` unless a change explicitly moves the style system. |

Generation orchestration belongs in `src/features/generation/hooks/useGenerationFlow.ts`. `PromptPanel` should remain presentational and receive the hook view model from `GenerationStudio`.
