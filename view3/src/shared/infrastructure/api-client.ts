// ─── API Client ───────────────────────────────────────────────
// Typed HTTP and WebSocket helpers for the generation backend.

import { env } from "./env.ts";
import type { GenerateRequest } from "@/features/chat/domain/dto";
import type { GenerateResponse } from "@/features/studio/domain/dto";

// ─── Constants ─────────────────────────────────────────────────

/** Timeout for all fetch calls: 30s to accommodate Modal cold-starts. */
const FETCH_TIMEOUT_MS = 30_000;

// ─── Types ────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  detail: string;
}

// ─── Helpers ──────────────────────────────────────────────────

/**
 * Map any thrown value to a stable `ApiError`.
 * Preserves AbortError as `timeout`, everything else as `client_error`.
 */
function toNetworkError(err: unknown): ApiError {
  if (err instanceof DOMException && err.name === "AbortError") {
    return { code: "timeout", detail: "Request timed out" };
  }
  return {
    code: "client_error",
    detail: err instanceof Error ? err.message : "Network request failed",
  };
}

// ─── Functions ────────────────────────────────────────────────

/**
 * POST a generation request to `{API_BASE_URL}/generate`.
 * Returns either the job response or a normalized error envelope.
 * Times out after `FETCH_TIMEOUT_MS` to handle Modal cold-starts.
 */
export async function submitGenerate(
  dto: GenerateRequest,
): Promise<GenerateResponse | ApiError> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(`${env.apiBaseUrl}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dto),
      signal: controller.signal,
    });

    // Parse body *before* clearing timeout so slow body reads still abort
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      clearTimeout(timeout);
      return normalizeError(res.status, body);
    }

    const data: GenerateResponse = await res.json();
    clearTimeout(timeout);
    return data;
  } catch (err) {
    clearTimeout(timeout);
    return toNetworkError(err);
  }
}

/**
 * Build the WebSocket URL for a given job ID.
 */
export function getWsUrl(jobId: string): string {
  return `${env.wsBaseUrl}/ws/generate/${jobId}`;
}

/**
 * Fetch image binary from the backend through the API base URL.
 * Returns the response on success, or an `ApiError` on network failure.
 * Times out after `FETCH_TIMEOUT_MS` to handle Modal cold-starts.
 */
export async function fetchImageBinary(
  jobId: string,
): Promise<Response | ApiError> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(`${env.apiBaseUrl}/images/${jobId}`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return res;
  } catch (err) {
    clearTimeout(timeout);
    return toNetworkError(err);
  }
}

/**
 * Normalize various backend error shapes into a stable `ApiError`.
 *
 * - 422 with `{ detail }`       → `{ code: "validation_error", detail }`
 * - 4xx with `{ error: { code, detail } }` → passthrough code + detail
 * - 5xx with `{ error: { code, detail } }` → passthrough code + detail (default code: "operational")
 * - Unknown shape               → `{ code: "unknown_error", detail: "Request failed" }`
 */
export function normalizeError(status: number, body: unknown): ApiError {
  const data = body as Record<string, unknown> | null;

  // 422 — validation detail (Pydantic-style)
  if (status === 422) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : "Validation failed";
    return { code: "validation_error", detail };
  }

  // 4xx — client error envelope
  if (status >= 400 && status < 500) {
    const error = data?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      return {
        code: error.code,
        detail:
          typeof error.detail === "string"
            ? error.detail
            : "Request failed",
      };
    }
    // Unknown shape → fallback
    return { code: "unknown_error", detail: "Request failed" };
  }

  // 5xx — server error envelope
  if (status >= 500) {
    const error = data?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      return {
        code: error.code,
        detail:
          typeof error.detail === "string"
            ? error.detail
            : "Request failed",
      };
    }
    // Unknown shape → fallback
    return { code: "unknown_error", detail: "Request failed" };
  }

  // Fallback
  return { code: "unknown_error", detail: "Request failed" };
}
