# Identity GGUF Workflows Specification

## Purpose

This spec defined the contract for Flux GGUF-based identity-preserving generation. All requirements are now REMOVED — the legacy `identidad_gguf` workflow has been replaced by the new identity flow (PuLID + FLUX on A100).

<!-- All requirements removed in sdd-2-modal-flows:
  (Reason: `identidad_gguf` is deprecated and replaced by Flow 3 — Identity/PuLID + FLUX.)
  (Migration: route callers to `POST /generate/identity`; the `api/src/workflows/identidad_gguf/` directory has been deleted.)

  Removed requirements:
  - Accept Identity GGUF Workflow Requests
  - Load Identity GGUF Workflow Manifest
  - Resolve Identity GGUF Parameters
  - GGUF Identity Generation Execution
  - Identity GGUF Checkpoint Whitelist Entry
  - GGUF Custom Node Installation

  See `openspec/specs/identity-workflows/spec.md` for the replacement.
-->
