// ─── API Client ───────────────────────────────────────────────
// Typed HTTP and WebSocket helpers for the generation backend.

import { env } from "./env.ts";
import { SESSION_COOKIE_NAME } from "./session.ts";
import {
  createPlanningBlockedStages,
  type GenerateRequest,
  type OrchestrateRequest,
  type OrchestrateResponse,
  type OrchestrateStage,
} from "../../features/chat/domain/dto.ts";
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

function syncSessionCookie(sessionId: string): void {
  if (typeof document === "undefined") return;

  const https =
    typeof window !== "undefined" &&
    typeof window.location !== "undefined" &&
    window.location.protocol === "https:";
  const cookie = [
    `${SESSION_COOKIE_NAME}=${encodeURIComponent(sessionId)}`,
    "Path=/",
    "SameSite=Lax",
    ...(https ? ["Secure"] : []),
  ].join("; ");

  document.cookie = cookie;
}

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
  try {
    let sid = localStorage.getItem(SESSION_COOKIE_NAME);
    if (!sid) {
      sid = crypto.randomUUID();
      localStorage.setItem(SESSION_COOKIE_NAME, sid);
    }
    syncSessionCookie(sid);
    return sid;
  } catch {
    if (!_sessionIdFallback) {
      _sessionIdFallback = crypto.randomUUID();
    }
    syncSessionCookie(_sessionIdFallback);
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

function toOrchestrateNetworkError(err: unknown): OrchestrateResponse {
  const apiError = toNetworkError(err);
  return {
    outcome: "error",
    error_code: apiError.code,
    error_detail: apiError.detail,
    stages: createPlanningBlockedStages(),
  };
}

function normalizeOrchestrateError(status: number, body: unknown): OrchestrateResponse {
  const data = body as Partial<OrchestrateResponse> | null;
  if (data?.outcome === "error") {
    return {
      outcome: "error",
      stages: data.stages ?? createPlanningBlockedStages(),
      error_code: data.error_code ?? "orchestration_error",
      error_detail: data.error_detail ?? "Orchestration failed",
    };
  }
  const error = normalizeError(status, body);
  return {
    outcome: "error",
    stages: createPlanningBlockedStages(),
    error_code: error.code,
    error_detail: error.detail,
  };
}

function safeOrchestrateErrorDetail(code: string | null | undefined, detail: string | null | undefined): string {
  switch (code) {
    case "planner_provider_invalid_response":
      return "Planning service returned an invalid response";
    case "planner_provider_unavailable":
      return "Planning service is unavailable";
    case "invalid_orchestration_response":
      return "Orchestration response was invalid";
    default:
      return detail || "Orchestration failed";
  }
}

function normalizeSuccessfulOrchestrateResponse(body: unknown): OrchestrateResponse {
  const data = body as Partial<OrchestrateResponse> | null;
  const stages: OrchestrateStage[] = Array.isArray(data?.stages) ? data.stages : createPlanningBlockedStages();
  if (!data || typeof data.outcome !== "string") {
    return {
      outcome: "error",
      stages: createPlanningBlockedStages(),
      error_code: "invalid_orchestration_response",
      error_detail: "Orchestration response was invalid",
    };
  }
  if (data.outcome === "job_started" && !data.job_id) {
    return {
      outcome: "error",
      stages,
      error_code: "invalid_orchestration_response",
      error_detail: "Orchestration response was invalid",
    };
  }
  if (data.outcome === "error") {
    const code = data.error_code ?? "orchestration_error";
    return {
      outcome: "error",
      stages,
      job_id: data.job_id ?? null,
      error_code: code,
      error_detail: safeOrchestrateErrorDetail(code, data.error_detail),
    };
  }
  if (["job_started", "clarification_required", "missing_asset"].includes(data.outcome)) {
    return { ...data, stages } as OrchestrateResponse;
  }
  return {
    outcome: "error",
    stages,
    error_code: "invalid_orchestration_response",
    error_detail: "Orchestration response was invalid",
  };
}

export async function submitOrchestrate(
  dto: OrchestrateRequest,
): Promise<OrchestrateResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const sid = getSessionId();
  if (sid) headers["X-Session-ID"] = sid;

  try {
    const res = await fetch(`${env.apiBaseUrl}/generate/orchestrate`, {
      method: "POST",
      headers,
      body: JSON.stringify(dto),
      signal: controller.signal,
    });

    const body = await res.json().catch(() => null);
    clearTimeout(timeout);
    if (!res.ok) {
      return normalizeOrchestrateError(res.status, body);
    }
    return normalizeSuccessfulOrchestrateResponse(body);
  } catch (err) {
    clearTimeout(timeout);
    return toOrchestrateNetworkError(err);
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
  /** Forwarded to `fetch` — auth endpoints set `"include"` so cross-origin cookies flow. */
  credentials?: RequestCredentials;
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
    credentials,
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
      ...(credentials !== undefined ? { credentials } : {}),
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
