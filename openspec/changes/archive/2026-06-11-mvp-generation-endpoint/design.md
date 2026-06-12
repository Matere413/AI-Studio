# Design: MVP Generation Endpoint

## Technical Approach

Implement a FastAPI application that exposes the `POST /generate` and `WS /ws/generate/{job_id}` endpoints. We will use Pydantic for request and WebSocket event validation as defined in the spec. For the generation task, we will define a Modal function stub that acts as the background worker. Job states and lifecycle events will be managed via a simple, abstract `JobStore` in the shared module, allowing the FastAPI WebSocket to poll or subscribe to job updates.

## Architecture Decisions

| Decision | Choice | Alternatives Considered | Rationale |
|---|---|---|---|
| **Async Task Execution** | Modal Functions (`@app.function`) | Celery, RQ | Required by specification to use Modal for compute-heavy tasks. |
| **State Management** | Abstract `JobStore` backed by `modal.Dict` (distributed key-value store) | Redis, Database, In-memory dict | Distributed store survives container restarts and is accessible from both API and GPU containers; `modal.Dict` requires no external infrastructure. Async access via `.get.aio()` prevents blocking warnings in WebSocket polling loops. |
| **WebSocket Handling** | FastAPI Native WebSockets | Starlette raw WS | FastAPI provides native WS support and integrates well with Pydantic validations. |

## Data Flow

```text
Client            FastAPI (API Router)          Modal Function
  |                       |                           |
  |--- POST /generate --->|                           |
  |   { prompt: ... }     |--- spawns async task ---->|
  |<--- 202 Accepted -----|                           |
  |                       |                           |
  |--- WS /ws/generate -->|                           |
  |<--- pending event ----|                           |
  |<--- running event ----|<---- updates state -------|
  |<--- completed event --|<---- completion ----------|
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/features/generation/router.py` | Create | FastAPI router exposing `POST /generate` and `WS /ws/generate/{job_id}` |
| `src/features/generation/models.py` | Create | Pydantic models for request (`GenerateRequest`), response (`GenerateResponse`), and WS events (`JobEvent`) |
| `src/features/generation/modal_tasks.py` | Create | Modal app and stub function (`@app.function`) for background image generation |
| `src/features/generation/service.py` | Create | Business logic to validate requests, spawn Modal tasks, and fetch job states |
| `src/shared/job_store.py` | Create | Abstract state manager to track job lifecycle states (`pending`, `running`, `completed`, `error`) |

## Interfaces / Contracts

```python
# src/features/generation/models.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)

class GenerateResponse(BaseModel):
    job_id: str
    status: Literal["pending"] = "pending"

class JobEventError(BaseModel):
    code: str
    detail: str

class JobEventResult(BaseModel):
    image_path: str = Field(..., min_length=1)

class JobEvent(BaseModel):
    event: Literal["pending", "running", "completed", "error"]
    job_id: str
    timestamp: str
    progress: Optional[int] = Field(None, ge=0, le=100)
    message: Optional[str] = None
    result: Optional[JobEventResult] = None
    error: Optional[JobEventError] = None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Validation models | Pytest with Pydantic validation (e.g., prompt length checks) |
| Integration | FastAPI Endpoints | `TestClient` for `POST /generate` and WebSocket streams, mocking the Modal job execution |
| E2E | End-to-end flow | Simulate WS connection, mock `JobStore` state updates, ensure terminal state disconnects stream |

## Migration / Rollout

No migration required. This is a new MVP endpoint.

## Resolved Questions

- [x] **Job state persistence**: `modal.Dict` distributed store provides cross-container visibility and survives restarts, keeping the MVP simple while being production-viable.
- [x] **Progress reporting**: Both API and GPU function containers share the same `modal.Dict` instance, so the API container polls the shared store directly — no webhook or external broker needed.
