# AI Studio - Unified Rules & Architecture

Este documento contiene las reglas unificadas de arquitectura y directrices de IA para todo el proyecto (Backend API y Frontend View).

## 🎨 Global UI/UX & Design Contract

Todas las reglas visuales (color, tipografía, espaciado, componentes, motion, anti-patrones) están definidas en:

> **[`./DESIGN.md`](./DESIGN.md)**

**Leer DESIGN.md antes de crear cualquier componente de UI.**

Resumen rápido:
- **Dark mode** siempre. No hay modo claro.
- **Sin sombras**. Usar bordes de 1px (`#2e2820`) para separar capas.
- **Sin gradients** ni fondos cálidos.
- **Sin emojis** como iconos. SVG de línea fina siempre.
- **Sin tipografías redondeadas**.
- **Accent**: `#d97706` (naranja ámbar). **Highlight**: `#eab208` (amarillo dorado).
- **Motion**: `150ms cubic-bezier(0.4, 0, 0.2, 1)`. Nada de springs.
- **Voz**: Técnica, directa. Preferir "Generación completada: 12.4s" sobre "¡Felicidades!".

---

## 🖥️ Frontend Architecture (Next.js View)

### Stack

| Capa         | Tecnología                                              |
| ------------ | ------------------------------------------------------- |
| Framework    | Next.js 14+ (App Router)                                |
| Lenguaje     | TypeScript (strict mode)                                |
| Estilos      | Tailwind CSS v3+                                        |
| UI Base      | Custom components sobre el design system de I-Studio    |
| Linting      | ESLint + Prettier                                       |

### Arquitectura: Hexagonal Feature-First

**Principio**: Cada feature es un módulo independiente con su propio dominio, aplicación e infraestructura. Las dependencias apuntan hacia adentro: las capas internas (domain) no conocen las externas (infrastructure).

### Estructura de directorios

```text
src/
├── shared/                    # Código compartido entre features
│   ├── domain/                # Tipos, interfaces, value objects genéricos
│   ├── application/           # Hooks, lógica reutilizable
│   └── infrastructure/        # Clientes HTTP, providers globales, config
│
├── features/
│   ├── auth/                  # Feature: Autenticación
│   │   ├── domain/            # Tipos de dominio (User, Session, etc.)
│   │   ├── application/       # Hooks, casos de uso
│   │   └── infrastructure/    # API calls, localStorage, etc.
│   │   └── presentation/      # Componentes de UI específicos del feature
│   │       ├── components/    # Componentes React
│   │       └── pages/         # Server Components / Pages
│   │
│   ├── studio/                # Feature: Workspace/Studio Canvas
│   ├── chat/                  # Feature: Agent Chat sidebar
│   ├── workflows/             # Feature: Workflow Library
│   └── assets/                # Feature: Asset gallery
│
├── app/                       # Next.js App Router (pages, layouts)
│   ├── layout.tsx             # Root layout global
│   ├── page.tsx               # Home / Dashboard
│   └── (routes)/              # Agrupar rutas por feature si aplica
│
└── middleware.ts              # Next.js middleware (auth, etc.)
```

### Reglas de dependencia
- `domain/`: NO importa nada de `application/`, `infrastructure/` ni `presentation/`. Solo tipos y lógica pura.
- `application/`: Importa de `domain/` y de `shared/domain/`. NO importa de `infrastructure/` ni `presentation/`.
- `infrastructure/`: Importa de `domain/` y `application/`. Implementa interfaces definidas en domain.
- `presentation/`: Importa de `application/`, `domain/` y `shared/`. Los componentes NO llaman infrastructure directamente.

### Convención de nomenclatura
- **Archivos**: `kebab-case`. Ej: `user-session.ts`, `auth-store.ts`
- **Componentes React**: `PascalCase`. Ej: `ChatSidebar.tsx`, `StudioCanvas.tsx`
- **Funciones y hooks**: `camelCase`. Ej: `useGenerationStatus()`, `formatPrompt()`
- **Tipos e interfaces**: `PascalCase` con prefijo `I` opcional para interfaces. Ej: `UserSession`, `WorkflowConfig`
- **Constantes**: `UPPER_SNAKE_CASE`. Ej: `MAX_FILE_SIZE`, `API_BASE_URL`

### Tailwind: Patrones de Uso

**Tema**: Usar siempre los tokens del `tailwind.config.js` definidos en DESIGN.md:
```tsx
// Bien ✅
<div className="bg-base text-primary border border-border" />

// Mal ❌
<div className="bg-[#1c1917] text-[#F5F5F5] border border-[#2e2820]" />
```

**Layout base de la app**:
```tsx
<div className="flex h-screen w-screen overflow-hidden bg-base">
  <aside className="w-[300px] border-r border-border bg-surface flex flex-col">
    {/* Chat / Agent sidebar */}
  </aside>
  <main className="flex-1 flex flex-col">
    <header className="h-12 border-b border-border flex items-center px-4">
      {/* Top bar */}
    </header>
    <div className="flex-1 overflow-auto p-6">
      {/* Studio canvas */}
    </div>
  </main>
</div>
```

**Botones**:
```tsx
// Primary
<button className="inline-flex items-center justify-center h-9 px-5 rounded-full bg-accent text-base text-sm font-medium transition-all duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2">
  Publish
</button>

// Secondary
<button className="inline-flex items-center justify-center h-9 px-5 rounded-full bg-transparent text-primary text-sm font-medium border border-border transition-all duration-studio ease-studio hover:bg-surface-hover hover:border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight">
  Export
</button>

// Ghost
<button className="inline-flex items-center justify-center h-9 px-2 rounded-full bg-transparent text-primary/70 text-sm transition-all duration-studio ease-studio hover:bg-surface-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight">
  <svg />
</button>
```

**Inputs**:
```tsx
<input
  className="w-full h-9 px-3 rounded-[8px] bg-surface text-primary text-sm border border-border placeholder:text-muted transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none"
  placeholder="Message Agent..."
/>
```

---

## ⚙️ Backend Architecture (Python API)

### 1. Stack Tecnológico
- **Lenguaje Base**: Python 3.10+
- **Infraestructura Cloud**: Modal (Serverless GPUs, Scale-to-Zero)
- **Motor Generativo**: ComfyUI (Modo Headless / API)
- **Servidor Web**: FastAPI (requiere instalación explícita de `fastapi[standard]` en Modal)
- **Integración Local/Testing**: `websocket-client` para rastreo asíncrono.

### 2. Patrones de Arquitectura
- **Enrutamiento Inteligente (Smart Routing)**: Un único endpoint ("Portero") recibe el payload, analiza el tipo de tarea y delega la ejecución a flujos especializados (JSONs de ComfyUI). No existe un "flujo general para todo".
- **Infraestructura como Código (IaC)**: Los contenedores de ejecución (Ladrillo), volúmenes de red (Sótano) y requerimientos de hardware (GPU T4/A100) se definen exclusivamente mediante decoradores de Modal en Python (`@app.function`, `@modal.fastapi_endpoint`).
- **Comunicación Asíncrona**: Las inferencias son de larga duración. El sistema prohíbe el bloqueo HTTP (*Timeout*). El backend debe aceptar el requerimiento, devolver un *Job ID* en milisegundos y, al finalizar la inferencia, disparar un **Webhook** al servidor del cliente.
- **Separación de Responsabilidades**: La capa de negocio (Backend) NO procesa IA; se limita a mutar diccionarios JSON e inyectar payloads. La capa de inferencia (ComfyUI) NO conoce el modelo de negocio, solo ejecuta grafos matemáticos.

### 3. Alcance del MVP
El producto debe soportar 3 "Cintas de Montaje" representadas por 3 archivos JSON independientes:
1. **Generación Base (Text-to-Image)**: Pipeline clásico a partir de texto.
2. **Edición (Inpainting)**: Pipeline de sustitución utilizando Imagen Original + Máscara + Prompt.
3. **Estructura (ControlNet)**: Pipeline de preservación utilizando mapas de profundidad o bordes para mantener la fidelidad de la imagen de referencia.

### 4. Reglas Estrictas de Desarrollo
- **Dependencias Explícitas**: Queda prohibida la "magia" en contenedores. Paquetes requeridos para el servidor web (`fastapi[standard]`) deben declararse explícitamente en el bloque `.run_commands()` del `modal.Image`.
- **Manejo de Modelos Pesados (Weights)**: Los archivos `.safetensors` (Checkpoints, LoRAs) jamás se incorporan en la imagen base de Docker. Se gestionan a través de un `modal.Volume` persistente para evitar latencias en el *Cold Start*.
- **Manejo de Tráfico de Imágenes**: Queda prohibido el tránsito de imágenes en Base64 pesado por las arterias principales de la API. Se prioriza subir a *object storage* (S3/R2) y operar con URLs.
- **Formato de Grafos**: Todo desarrollo visual en ComfyUI debe exportarse obligatoriamente con la opción "Save (API format)". El backend interactúa operando sobre IDs de nodos (ej. `"3"`, `"6"`), no mediante la interfaz visual.

---

## 🧪 Testing
- Tests unitarios con Vitest para lógica de domain y application
- Tests de componentes con React Testing Library
- Tests E2E con Playwright (cuando aplique)
- Los tests viven dentro de cada feature: `features/<name>/**/*.test.ts`

## 📦 Commits y PRs
- **Commits**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`)
- **PRs**: En inglés. Incluir screenshot de cambios visuales.
- **AI attribution**: No incluir "Co-Authored-By" ni atribución de IA.

## 🛠️ Skills / Referencias
Este proyecto usa las skills de OpenCode para diseño y desarrollo:
- `frontend-design` — para componentes de alta calidad visual
- `impeccable` — para pulido y revisión de UI
- `apple-ui-skills` — inspiración en estética Apple (cuando aplique)
- `shadcn-ui` — solo si se decide integrar shadcn/ui (no es el default)
