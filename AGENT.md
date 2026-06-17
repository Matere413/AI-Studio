# AI Studio - Unified Rules & Architecture

Este documento contiene las reglas unificadas de arquitectura y directrices de IA para todo el proyecto (Backend API y Frontend View).

## 🎨 Global UI/UX & Design Contract
- **Design System Reference**: ALL frontend views, components, and interactive elements MUST strictly follow `matere-design-system` as the single source of truth for design. Do not invent ad-hoc styles. 
- **Regla Estricta Front-end**: Siempre que se toque, modifique o cree código del frontend, es **obligatorio** usar `matere-design-system` como referencia visual y estructural.
- Align visually and behaviorally with established primitives, typography scale, spacing, and border-radius (Apple-inspired UI if specified by the system).

## 🖥️ Frontend Architecture (Next.js View)

### This is NOT the Next.js you know
This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

### Feature-first conventions
- **Generation Feature**: Put API clients, types, hooks, stores, components, CSS modules, and tests under `src/features/generation/`.
- **Shared UI**: Put reusable, domain-agnostic UI primitives under `src/shared/components/ui/`.
- **App routes**: Keep `src/app/` thin. Route files should focus on composition and import feature entry components.
- **Global styles**: Keep global design-system CSS under `src/styles/` unless explicitly moved.
- **Orchestration**: Generation flow belongs in `src/features/generation/hooks/useGenerationFlow.ts`. Components like `PromptPanel` should remain presentational.

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

### 5. Estructura de Directorios (Arquitectura Hexagonal)
Para mantener el aislamiento estricto entre el dominio de negocio y la infraestructura, el proyecto implementará la siguiente estructura de carpetas:

```text
src/
├── features/
│   ├── generation/       # Feature: Generación base (Texto-a-Imagen).
│   ├── inpainting/       # Feature: Edición (Máscara + Foto).
│   └── controlnet/       # Feature: Preservación de estructura.
│       # *Dentro de cada feature conviven sus propios casos de uso, rutas API y adaptadores específicos.
├── shared/               # Código transversal: Clientes base (Modal, ComfyUI), Configuración, Tipos.
└── tests/                # Tests de integración y unitarios por feature.
```