# Exploration: MVP Generation Endpoint

## 1. Goal
Implement a Base Image Generation API endpoint using a ComfyUI JSON workflow on Modal, tracking progress via WebSockets, following a Feature-First architecture.

## 2. Current State
- `app.py`: Contains basic Modal image definitions and a stubbed `@modal.fastapi_endpoint`.
- `api.py`: Contains a synchronous WebSocket client talking to a local ComfyUI server (`127.0.0.1:8188`).
- `payload.json`: Example ComfyUI JSON workflow payload.

## 3. Feature-First Structure Proposal
```
src/
  features/
    generation/
      __init__.py
      router.py          # FastAPI routes (POST /generate, WS /ws/generate/{job_id})
      services.py        # Business logic, ComfyUI payload assembly
      modal_jobs.py      # Modal GPU background functions (@app.function)
      models.py          # Pydantic schemas for requests/responses
  shared/
    modal_config.py      # Shared Modal App and Image definitions
    comfy_client.py      # Common ComfyUI interaction utilities
```

## 4. Technical Integration Analysis
- **FastAPI Router:** Define an ASGI app using `modal.asgi_app` instead of a basic `fastapi_endpoint`. This allows routing and WebSocket support in one place.
- **Modal Integration:**
  - The API container runs on standard CPU.
  - The generation task runs on a GPU via a background Modal function (`generador_job.spawn(...)`).
- **ComfyUI JSON Workflow:** 
  - Parse `payload.json` and inject dynamic prompts via Pydantic models.
  - The GPU function boots up ComfyUI locally inside the container, posts the JSON to `127.0.0.1:8188`, and waits for completion using `api.py`'s websocket logic.
- **WebSocket for Job Tracking:** The client connects to the FastAPI ASGI container via WS. Since Modal functions run asynchronously, the API container needs to know the progress.

## 5. Approaches for WebSocket / Modal Interaction
### Approach A: FastAPI Polling Modal Call ID (Recommended)
- Client sends POST request, receives `job_id` (Modal Call ID).
- Client connects to WS endpoint `/ws/status/{job_id}`.
- The FastAPI WS handler loops and checks the status of the Modal job using Modal's client APIs, sending updates down the WS.
- **Pros:** Stateless API container, simple architecture.
- **Cons:** Polling is less efficient.

### Approach B: Redis / PubSub Broker
- The GPU function publishes progress to a Redis instance.
- The FastAPI WS endpoint subscribes to the Redis channel for that `job_id` and forwards to the client.
- **Pros:** Real-time push updates.
- **Cons:** Requires provisioning and managing a Redis instance/broker on Modal or externally, adding infrastructure overhead for an MVP.
