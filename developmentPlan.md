# Plan de Desarrollo: AI Studio (Marketing & Advertising Platform)

Este documento define la hoja de ruta del proyecto dividida en iniciativas independientes. Cada bloque representa un ciclo completo de **SDD (Spec-Driven Development)**. Al finalizar un bloque, se archiva (`sdd-archive`) y se avanza al siguiente, garantizando que no perdamos el foco ni mezclemos responsabilidades.

---

## 💅 SDD 1: Migración UI Actual (Design System Refactor)
**Estado:** `[x] Completado`

*Pagar la deuda técnica visual antes de construir nuevas features, alineando todo el frontend existente a la nueva guía de estilos.*

*   **Objetivos:**
    *   Auditar las vistas y componentes actuales en `view/` (o la carpeta de frontend).
    *   Reemplazar componentes, colores, tipografías y espaciados basados en el obsoleto `matere-design-system`.
    *   Implementar los tokens y primitives estrictos de `ai-studio-design-system`.
*   **Criterio de Éxito:** La aplicación actual compila y se ve 100% fiel al nuevo sistema de diseño, sin código CSS heredado (legacy) ni componentes visualmente rotos.

---

## 📦 SDD 2: Librería de Flujos Base y Estandarización Modal (Calidad Core)
**Estado:** `[ ] Pendiente`

*El objetivo de este ciclo es garantizar que la calidad de salida sea "nivel agencia publicitaria" usando los flujos de ComfyUI como APIs atómicas.*

*   **Objetivos:**
    *   Limpiar y estandarizar los flujos actuales en formato JSON (API).
    *   Implementar flujo de **Extracción/Aislamiento** (Rembg/BRIA para recorte de productos).
    *   Implementar flujo de **Composición** usando FLUX + ControlNet (Depth/Canny) para integrar productos en escenarios generados sin deformar el empaque.
    *   Implementar flujo de **Identidad** (IP-Adapter/FaceID) para personajes recurrentes.
*   **Criterio de Éxito:** Podemos enviar JSONs estáticos a Modal a través de la API en Python y obtener imágenes fotorrealistas de alta gama, preservando formas e identidades.

---

## 🗄️ SDD 3: Sistema de Workspaces y Gestión de Assets
**Estado:** `[ ] Pendiente`

*La plataforma requiere que los usuarios gestionen sus proyectos y recursos (imágenes, personajes) para que el Orquestador tenga contexto.*

*   **Objetivos:**
    *   Diseñar esquema de base de datos para `Projects` y `Assets`.
    *   Implementar subida de archivos directa a Object Storage (S3/R2) desde el frontend.
    *   Modificar la API de Python para que los payloads de ComfyUI consuman URLs de S3 en lugar de Base64 pesado.
*   **Criterio de Éxito:** Un usuario puede crear un proyecto, subir imágenes de referencia, y la base de datos las vincula correctamente con URLs públicas/firmadas.

---

## 🧠 SDD 4: Agente Orquestador (El Cerebro LLM)
**Estado:** `[ ] Pendiente`

*El traductor que convierte intenciones humanas y assets en grafos matemáticos para ComfyUI.*

*   **Objetivos:**
    *   Crear el servicio de enrutamiento inteligente usando un LLM (ej. gpt-4o / claude-3.5-sonnet).
    *   Implementar el prompt del sistema que instruye al LLM sobre cómo interpretar el pedido del usuario y qué JSON de ComfyUI elegir (Extracción, Composición, Edición).
    *   Lógica de inyección: El backend toma la decisión del LLM, inyecta los IDs de los Assets y dispara el Job a Modal.
*   **Criterio de Éxito:** Se le envía un texto libre y una lista de Asset IDs al backend, y este ensambla y ejecuta correctamente la cadena de nodos en Modal sin intervención humana técnica.

---

## 🎨 SDD 5: Interfaz Híbrida y UX Asíncrona (Nuevas Vistas)
**Estado:** `[ ] Pendiente`

*La experiencia de usuario final en Next.js, combinando la "magia" del chat con el control manual del canvas, gestionando la latencia inteligentemente.*

*   **Objetivos:**
    *   Construir la vista del **Workspace** (Sidebar con assets).
    *   Construir el **Chat** para la interacción inicial con el Orquestador.
    *   Construir el **Canvas Iterativo**, permitiendo al usuario pintar máscaras (brush) para envíos de Inpainting.
    *   Implementar el manejo asíncrono (Webhooks/Polling) con esqueletos de carga detallados ("Analizando...", "Recortando...", "Generando...").
*   **Criterio de Éxito:** El diseñador puede interactuar fluidamente usando los componentes del `ai-studio-design-system` creados en el SDD 1.