# AI-Studio

**AI-powered creative workspace** — a serverless generative media platform built on ComfyUI, Modal, FastAPI, and Next.js.

Generate, edit, and manipulate images through a clean studio interface backed by GPU-accelerated inference pipelines.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    View (Next.js)                    │
│         React 18 · TypeScript · Tailwind CSS         │
├─────────────────────────────────────────────────────┤
│               API (FastAPI · Python)                 │
│        Smart routing · Webhooks · Job queue          │
├─────────────────────────────────────────────────────┤
│            Inference (ComfyUI · Modal)                │
│       Serverless GPU (T4/A100) · Scale-to-zero        │
└─────────────────────────────────────────────────────┘
```

### Backend
- **FastAPI** with async endpoint routing
- **Modal** for serverless GPU inference (scale-to-zero, no cold-start volumes)
- **ComfyUI** headless API for generative workflows
- Async job model: accept → return Job ID → webhook on completion
- Smart router delegates payloads to specialized pipeline JSONs

### Frontend
- **Next.js 14** (App Router) with strict TypeScript
- **Tailwind CSS v3** — dark-mode-only design system
- Hexagonal feature-first architecture
- Prompt-first orchestration UI

## Pipelines

| Pipeline       | Description                                     |
| -------------- | ----------------------------------------------- |
| Text-to-Image  | Generate images from text prompts               |
| Inpainting     | Edit specific regions using mask + prompt       |
| ControlNet     | Structure-preserving generation (depth, edges)  |

## Getting started

### Prerequisites
- Python 3.10+
- Node.js 20+
- pnpm 8+

### Backend
```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
modal deploy app.py
```

### Frontend
```bash
cd view
pnpm install
pnpm dev
```

## Project structure

```text
.
├── api/                    # Python backend (FastAPI + Modal)
│   ├── app.py             # Entrypoint, Modal deployment
│   └── src/               # Hexagonal feature modules
├── view/                   # Next.js frontend
│   └── src/               # Feature-based architecture
├── openspec/               # SDD specs and change artifacts
```

## License

MIT
