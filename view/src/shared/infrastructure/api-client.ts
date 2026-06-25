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

// ─── Session ID ───────────────────────────────────────────────

/**
 * In-memory fallback when localStorage is unavailable (private browsing,
 * quota exceeded, disabled storage).
 */
let _sessionIdFallback: string | null = null;

/**
 * Read or generate a stable session identifier, persisted in localStorage.
 *
 * The session ID is included as the ``X-Session-ID`` header on every
 * API request so the backend can validate artifact ownership and enforce
 * cross-session boundaries.
 *
 * Falls back to a module-scoped in-memory variable when localStorage
 * throws (e.g. quota exceeded, disabled in private mode).
 */
function getSessionId(): string {
  if (typeof window === "undefined") return "";
  const STORAGE_KEY = "ai-studio-session-id";
  try {
    let sid = localStorage.getItem(STORAGE_KEY);
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem(STORAGE_KEY, sid);
    }
    return sid;
  } catch {
    if (!_sessionIdFallback) {
      _sessionIdFallback = crypto.randomUUID();
    }
    return _sessionIdFallback;
  }
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

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const sid = getSessionId();
  if (sid) headers["X-Session-ID"] = sid;

  try {
    const res = await fetch(`${env.apiBaseUrl}/generate`, {
      method: "POST",
      headers,
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
 * Appends the session_id as a query parameter so the backend can enforce
 * session ownership on WebSocket connections.
 */
export function getWsUrl(jobId: string): string {
  const sid = getSessionId();
  let url = `${env.wsBaseUrl}/ws/generate/${jobId}`;
  if (sid) url += `?session_id=${encodeURIComponent(sid)}`;
  return url;
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

  const headers: Record<string, string> = {};
  const sid = getSessionId();
  if (sid) headers["X-Session-ID"] = sid;

  try {
    const res = await fetch(`${env.apiBaseUrl}/images/${jobId}`, {
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return res;
  } catch (err) {
    clearTimeout(timeout);
    return toNetworkError(err);
  }
}

// ─── fetchWithSession ─────────────────────────────────────────

/**
 * Options for `fetchWithSession`.
 */
export interface FetchWithSessionOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: BodyInit | null;
  headers?: Record<string, string>;
  timeoutMs?: number;
}

/**
 * Wrapped `fetch` that automatically attaches `X-Session-ID`,
 * applies a timeout, and returns a normalized `Response`.
 *
 * On network errors (timeout, DNS, CORS) it throws an `ApiError`.
 * HTTP non-ok statuses are returned as-is — callers inspect `res.ok`.
 */
export async function fetchWithSession(
  url: string,
  opts: FetchWithSessionOptions = {},
): Promise<Response> {
  const {
    method = "GET",
    body = null,
    headers = {},
    timeoutMs = FETCH_TIMEOUT_MS,
  } = opts;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const allHeaders: Record<string, string> = {
    ...headers,
  };
  // Only set Content-Type for non-GET requests with body
  if (body && method !== "GET" && !headers["Content-Type"]) {
    allHeaders["Content-Type"] = "application/json";
  }
  const sid = getSessionId();
  if (sid) allHeaders["X-Session-ID"] = sid;

  try {
    const res = await fetch(url, {
      method,
      headers: allHeaders,
      body,
      signal: controller.signal,
    });
    clearTimeout(timeout);
    return res;
  } catch (err) {
    clearTimeout(timeout);
    throw toNetworkError(err);
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
