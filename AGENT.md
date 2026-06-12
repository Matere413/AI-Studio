# Proyecto: API Blanca B2B (Estudio Generativo)

## 1. Stack Tecnológico
- **Lenguaje Base**: Python 3.10+
- **Infraestructura Cloud**: Modal (Serverless GPUs, Scale-to-Zero)
- **Motor Generativo**: ComfyUI (Modo Headless / API)
- **Servidor Web**: FastAPI (requiere instalación explícita de `fastapi[standard]` en Modal)
- **Integración Local/Testing**: `websocket-client` para rastreo asíncrono.

## 2. Patrones de Arquitectura
- **Enrutamiento Inteligente (Smart Routing)**: Un único endpoint ("Portero") recibe el payload, analiza el tipo de tarea y delega la ejecución a flujos especializados (JSONs de ComfyUI). No existe un "flujo general para todo".
- **Infraestructura como Código (IaC)**: Los contenedores de ejecución (Ladrillo), volúmenes de red (Sótano) y requerimientos de hardware (GPU T4/A100) se definen exclusivamente mediante decoradores de Modal en Python (`@app.function`, `@modal.fastapi_endpoint`).
- **Comunicación Asíncrona**: Las inferencias son de larga duración. El sistema prohíbe el bloqueo HTTP (*Timeout*). El backend debe aceptar el requerimiento, devolver un *Job ID* en milisegundos y, al finalizar la inferencia, disparar un **Webhook** al servidor del cliente.
- **Separación de Responsabilidades**: La capa de negocio (Backend) NO procesa IA; se limita a mutar diccionarios JSON e inyectar payloads. La capa de inferencia (ComfyUI) NO conoce el modelo de negocio, solo ejecuta grafos matemáticos.

## 3. Alcance del MVP
El producto debe soportar 3 "Cintas de Montaje" representadas por 3 archivos JSON independientes:
1. **Generación Base (Text-to-Image)**: Pipeline clásico a partir de texto.
2. **Edición (Inpainting)**: Pipeline de sustitución utilizando Imagen Original + Máscara + Prompt.
3. **Estructura (ControlNet)**: Pipeline de preservación utilizando mapas de profundidad o bordes para mantener la fidelidad de la imagen de referencia.

## 4. Reglas Estrictas de Desarrollo
- **Dependencias Explícitas**: Queda prohibida la "magia" en contenedores. Paquetes requeridos para el servidor web (`fastapi[standard]`) deben declararse explícitamente en el bloque `.run_commands()` del `modal.Image`.
- **Manejo de Modelos Pesados (Weights)**: Los archivos `.safetensors` (Checkpoints, LoRAs) jamás se incorporan en la imagen base de Docker. Se gestionan a través de un `modal.Volume` persistente para evitar latencias en el *Cold Start*.
- **Manejo de Tráfico de Imágenes**: Queda prohibido el tránsito de imágenes en Base64 pesado por las arterias principales de la API. Se prioriza subir a *object storage* (S3/R2) y operar con URLs.
- **Formato de Grafos**: Todo desarrollo visual en ComfyUI debe exportarse obligatoriamente con la opción "Save (API format)". El backend interactúa operando sobre IDs de nodos (ej. `"3"`, `"6"`), no mediante la interfaz visual.

## 5. Estructura de Directorios (Arquitectura Hexagonal)
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