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
 * Detect HTML markup (tags or declarations) inside an error detail string.
 *
 * Narrower than a naive "contains `<`" check: ordinary text with
 * angle-bracket comparisons (e.g. "Value must be < 100") is preserved
 * because the `<` is not immediately followed by a tag name. This matches
 * actual HTML markup only:
 *   - opening/closing tags: `<script>`, `</script>`, `<div>`,
 *     `<div class="x">`, `<br/>`
 *   - declarations/comments: `<!DOCTYPE html>`, `<!-- ... -->`
 *
 * A legitimate backend detail does not contain these; a proxy/framework
 * debug page (full document OR a fragment such as `<script>` / `<div>`)
 * does and MUST fall back so unsafe HTML is never surfaced to callers.
 */
const HTML_MARKUP_RE = /<\/?[a-zA-Z][\w:-]*(?:\s[^<>]*?)?\/?>|<!--|<!doctype/i;

function containsHtmlMarkup(value: string): boolean {
  return HTML_MARKUP_RE.test(value);
}

/**
 * Select a safe user-visible detail string, or fall back to a generic
 * message.
 *
 * `candidate` is accepted ONLY when it is a non-empty string that does not
 * contain HTML markup (tags such as `<script>` / `<div>`, or declarations
 * such as `<!DOCTYPE`). Non-string structures (objects, numbers, arrays)
 * and any string carrying HTML markup are rejected so unsafe bodies are
 * never surfaced to callers — the generic `fallback` is returned instead.
 * Ordinary text with angle-bracket comparisons (e.g. "Value must be < 100")
 * is preserved because it is not markup.
 *
 * Centralised so EVERY source of user-visible `detail` (422 top-level
 * detail, `{ error: { detail } }` envelopes for 4xx/5xx, and plain
 * top-level `detail` for 4xx/5xx) goes through the exact same guard.
 */
function safeDetailOr(
  candidate: unknown,
  fallback: string,
): string {
  if (typeof candidate !== "string" || candidate.length === 0) return fallback;
  if (containsHtmlMarkup(candidate)) return fallback;
  return candidate;
}

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
  /**
   * Forwarded to `fetch`. Defaults to `"include"` so the cross-origin auth
   * cookies (`ai-studio-auth` / `ai-studio-refresh`) flow on every call —
   * non-auth callers (e.g. `createProject`) rely on this default rather than
   * passing it explicitly. Pass `"omit"` to opt out.
   */
  credentials?: RequestCredentials;
}

// ─── Refresh-on-401 transparent retry (slice 4) ────────────────
//
// When an access token expires (15min JWT), protected endpoints return 401.
// The wrapper transparently calls POST /auth/refresh once (the refresh
// cookie is scoped to /auth and sent automatically via credentials:
// "include"), then retries the original request. Concurrent 401s during an
// in-flight refresh are queued and replayed after the refresh resolves.
// The /auth/refresh endpoint itself is exempt (loop guard — a 401 from
// refresh means the refresh token is also dead, so the session-expired
// handler fires and no second refresh is attempted).
//
// On refresh failure (401/403) the wrapper calls the registered
// `sessionExpiredHandler` so AuthProvider can clear auth state + redirect
// to /login. Callers see the original 401 pass through.

let isRefreshing = false;
// Each queued entry holds the (resolve, reject) of the waiting Promise +
// the (url, init) needed to replay it. On refresh SUCCESS we replay
// (resolve the retried response); on refresh FAILURE we REJECT without
// fetching — replaying a dead-session request would be a duplicate call
// against a session we already know is expired.
let refreshAndRetryQueue: Array<{
  resolve: (res: Response) => void;
  reject: (err: unknown) => void;
  url: string;
  init: RequestInit;
}> = [];
let sessionExpiredHandler: (() => void) | null = null;

/**
 * Register the session-expired callback. AuthProvider calls this on mount
 * so the api-client can clear auth state + redirect to /login when a
 * refresh fails. Decoupling the redirect from the api-client keeps the
 * client free of React/router imports.
 */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

/**
 * Reset the refresh state. Test-only hook so each test starts with a clean
 * `isRefreshing=false` and empty queue. Not exported via the public surface
 * (only tests import it directly).
 */
export function _resetRefreshState(): void {
  isRefreshing = false;
  refreshAndRetryQueue = [];
}

// 4R CRITICAL 4 — timeout for the retried request after a successful
// refresh. Without it, a hung retry leaves isRefreshing=true forever and
// the queue never drains. Default 30s; overridable via RETRY_TIMEOUT_MS
// (re-read per call so tests can override it after module load). On
// timeout the wrapper treats the retry as a refresh failure: drains the
// queue with rejections, resets isRefreshing, fires session-expired.
function getRetryTimeoutMs(): number {
  const raw = process.env.RETRY_TIMEOUT_MS;
  if (raw === undefined) return 30_000;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 30_000;
}

/**
 * 4R CRITICAL 4 — fetch with a timeout. Rejects with an `ApiError` when
 * the request does not settle within `timeoutMs`. Used for the retried
 * request after a successful refresh so a hung backend cannot pin
 * `isRefreshing=true` and stall the queue forever.
 *
 * Uses an AbortController for real-fetch cancellation AND a Promise race
 * as a belt-and-suspenders guard (so a fetch that ignores the abort signal
 * — e.g. a mock in tests — still times out). The timeout rejects with an
 * ApiError carrying code "timeout" so handle401 can distinguish a hang
 * from a network error and fire the session-expired path.
 */
async function doFetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const retryInit: RequestInit = {
    ...init,
    signal: controller.signal,
  };
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  // Race the fetch against a timer. The timer resolves FIRST on a hang,
  // rejecting this call with a timeout ApiError. The abort() is best-effort
  // (real fetches observe it; mocks may not, but the race covers that).
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      reject({ code: "timeout", detail: "Retried request timed out" } satisfies ApiError);
    }, timeoutMs);
  });
  try {
    return await Promise.race([fetch(url, retryInit), timeoutPromise]);
  } catch (err) {
    // If the fetch itself aborted (real fetch + signal), surface the
    // normalised ApiError. If the race's timer won, err is already the
    // timeout ApiError. Both flow through as a timeout/network failure.
    if (err && typeof err === "object" && "code" in err) throw err;
    throw toNetworkError(err);
  } finally {
    clearTimeout(timeout);
    if (timer) clearTimeout(timer);
  }
}

/**
 * Build the fetch init for a (re)try. Centralised so the retry uses the
 * exact same headers + credentials as the original.
 */
function buildFetchInit(
  method: string,
  body: BodyInit | null,
  headers: Record<string, string>,
  credentials: RequestCredentials,
  signal: AbortSignal,
): RequestInit {
  const allHeaders: Record<string, string> = { ...headers };
  if (body && method !== "GET" && !headers["Content-Type"]) {
    allHeaders["Content-Type"] = "application/json";
  }
  const sid = getSessionId();
  if (sid) allHeaders["X-Session-ID"] = sid;
  return {
    method,
    headers: allHeaders,
    body,
    credentials,
    signal,
  };
}

/**
 * Perform one fetch attempt with the given init. Returns the Response or
 * throws a normalised ApiError on network failure. Kept as a helper so the
 * original request and the retry use identical call shape.
 */
async function doFetch(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err) {
    throw toNetworkError(err);
  }
}

/**
 * Trigger a single POST /auth/refresh (cookies sent via credentials:
 * "include"). Returns the refresh Response. Used by the refresh-on-401
 * wrapper. Does NOT itself trigger another refresh (loop guard).
 */
async function callRefresh(): Promise<Response> {
  // Fresh AbortController for the refresh — the original request's signal
  // may have timed out already.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    return await fetch(`${env.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * 4R CRITICAL 5 — classify a failed refresh response as race-recoverable.
 * When two tabs refresh concurrently, one wins (rotates the cookie) and
 * the other gets ``invalid_refresh_token`` or ``token_revoked``. The loser
 * would be logged out despite a valid session. Mitigation: retry the
 * refresh ONCE — the winning tab's new cookie may now be present. A
 * BroadcastChannel is the proper cross-tab fix for follow-up.
 *
 * Only 401 with these specific codes are race-recoverable; a 403 or any
 * other failure means the session is genuinely dead (do not retry).
 */
async function isRaceRecoverable(res: Response): Promise<boolean> {
  if (res.status !== 401) return false;
  try {
    const body = (await res.clone().json()) as Record<string, unknown>;
    const code = (body?.error as Record<string, unknown> | undefined)?.code;
    return code === "invalid_refresh_token" || code === "token_revoked";
  } catch {
    return false;
  }
}

/**
 * Handle a 401 response: trigger refresh (or queue if one is in-flight),
 * retry the original on success, fire the session-expired handler on
 * refresh failure. The /auth/refresh URL is exempt (loop guard).
 */
async function handle401(
  url: string,
  init: RequestInit,
  originalResponse: Response,
): Promise<Response> {
  // Loop guard: the refresh endpoint itself MUST NOT trigger another refresh.
  // A 401 from /auth/refresh means the refresh cookie is also dead — return
  // the 401 to the caller (auth-api's refreshTokens() will throw).
  if (url === `${env.apiBaseUrl}/auth/refresh`) {
    return originalResponse;
  }

  // If a refresh is already in-flight, queue this request and await its
  // resolution. After the refresh succeeds, the queued request is
  // retried; if the refresh fails, the queued request is rejected (NOT
  // replayed — replaying against a dead session would be a duplicate).
  if (isRefreshing) {
    return new Promise<Response>((resolve, reject) => {
      refreshAndRetryQueue.push({ resolve, reject, url, init });
    });
  }

  // No refresh in-flight — start one.
  isRefreshing = true;
  try {
    // 4R CRITICAL 5 — multi-tab refresh race. Two tabs calling /auth/refresh
    // concurrently race; one wins (rotates the cookie), the other gets
    // invalid_refresh_token / token_revoked and would be logged out despite
    // a valid session. Mitigation: when the first refresh fails with a
    // race-recoverable code, retry ONCE more — the winning tab's new cookie
    // may now be present in the cookie jar. If the second also fails, the
    // session is genuinely dead and we fall through to the failure path.
    // A BroadcastChannel is the proper cross-tab fix for follow-up.
    let refreshRes = await callRefresh();
    if (!refreshRes.ok && (await isRaceRecoverable(refreshRes))) {
      refreshRes = await callRefresh();
    }
    if (refreshRes.ok) {
      // Refresh succeeded — retry the original request WITH a timeout
      // (4R CRITICAL 4). A hung retry would otherwise leave isRefreshing
      // pinned and the queue never drains. On timeout we fall through to
      // the failure path (reject queue + fire session-expired).
      let retried: Response;
      try {
        retried = await doFetchWithTimeout(url, init, getRetryTimeoutMs());
      } catch (retryErr) {
        // The retried request timed out (or threw a network error). A
        // timeout (code "timeout") means the backend hung — treat it as
        // a refresh failure: drain the queue with rejections + fire
        // session-expired so the user is bounced to /login (a hung retry
        // would otherwise pin isRefreshing forever).
        const isTimeout = (retryErr as { code?: string })?.code === "timeout";
        const queued = refreshAndRetryQueue.splice(0);
        const failure = isTimeout ? new Error("Session expired") : retryErr;
        queued.forEach((entry) => entry.reject(failure));
        if (isTimeout && sessionExpiredHandler) {
          sessionExpiredHandler();
        }
        // Re-throw so the lead caller also sees the failure.
        throw retryErr;
      }
      // Drain the queue: replay every queued request now that fresh
      // cookies are in place. Each entry's resolve/reject is bound to
      // its own waiting Promise; we do the fetch here and resolve.
      // 4R CRITICAL 4 — each replay is also timeout-guarded.
      const queued = refreshAndRetryQueue.splice(0);
      await Promise.all(
        queued.map(async (entry) => {
          try {
            entry.resolve(await doFetchWithTimeout(entry.url, entry.init, getRetryTimeoutMs()));
          } catch (err) {
            entry.reject(err);
          }
        }),
      );
      return retried;
    }
    // Refresh failed (401/403) — the session is dead. Fire the
    // session-expired handler so AuthProvider clears state + redirects.
    if (sessionExpiredHandler) {
      sessionExpiredHandler();
    }
    // Reject the queued requests — they were waiting for a refresh that
    // never succeeded. Reject WITHOUT fetching (no duplicate replay).
    const queued = refreshAndRetryQueue.splice(0);
    const failure = new Error("Session expired");
    queued.forEach((entry) => entry.reject(failure));
    return originalResponse;
  } finally {
    isRefreshing = false;
  }
}

/**
 * Wrapped `fetch` that automatically attaches `X-Session-ID`,
 * applies a timeout, transparently refreshes on 401, and returns a
 * normalized `Response`.
 *
 * On network errors (timeout, DNS, CORS) it throws an `ApiError`.
 * HTTP non-ok statuses are returned as-is — callers inspect `res.ok`.
 * A 401 triggers a single transparent /auth/refresh + retry (unless the
 * 401 is from /auth/refresh itself — loop guard).
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
    credentials = "include",
  } = opts;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const init = buildFetchInit(method, body, headers, credentials, controller.signal);

  try {
    const res = await fetch(url, init);
    clearTimeout(timeout);
    // Slice 4 — transparent refresh-on-401 retry. The loop guard inside
    // handle401 ensures /auth/refresh 401s pass through without recursion.
    if (res.status === 401) {
      return handle401(url, init, res);
    }
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
 * - 5xx with `{ error: { code, detail } }` → passthrough code + detail
 * - 4xx/5xx with a plain string `detail`  → `{ code: "unknown_error", detail }`
 *   (covers FastAPI/Starlette plain `{ detail }` bodies that don't use the
 *   `{ error: { code, detail } }` envelope, e.g. 400/401/403/409/429/5xx)
 * - Unknown shape               → `{ code: "unknown_error", detail: "Request failed" }`
 *
 * Every source of user-visible `detail` — the 422 top-level `detail`, the
 * `{ error: { detail } }` envelope for 4xx/5xx, and the plain top-level
 * `detail` for 4xx/5xx — goes through the same `safeDetailOr` guard. Only
 * a safe string `detail` (non-empty, free of HTML markup) is preserved;
 * non-string structures and any string carrying HTML markup (full document
 * or fragment such as `<script>` / `<div>`) fall back to the generic
 * message for that path so unsafe HTML is never surfaced to callers.
 * Envelope priority and existing stable codes are preserved when the detail
 * is safe.
 */
export function normalizeError(status: number, body: unknown): ApiError {
  const data = body as Record<string, unknown> | null;

  // 422 — validation detail (Pydantic-style). The detail is gated by the
  // same HTML-markup/safe-string guard as every other path; an unsafe 422
  // detail (e.g. a proxy HTML page or fragment) falls back to
  // "Validation failed".
  if (status === 422) {
    return {
      code: "validation_error",
      detail: safeDetailOr(data?.detail, "Validation failed"),
    };
  }

  // 4xx — client error envelope (priority over plain detail).
  if (status >= 400 && status < 500) {
    const error = data?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      return {
        code: error.code,
        detail: safeDetailOr(error.detail, "Request failed"),
      };
    }
    // Plain `{ detail: "..." }` (no envelope) — preserve a safe string
    // detail, keep the stable `unknown_error` code.
    if (typeof data?.detail === "string") {
      return { code: "unknown_error", detail: safeDetailOr(data.detail, "Request failed") };
    }
    // Unknown shape → fallback
    return { code: "unknown_error", detail: "Request failed" };
  }

  // 5xx — server error envelope (priority over plain detail).
  if (status >= 500) {
    const error = data?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      return {
        code: error.code,
        detail: safeDetailOr(error.detail, "Request failed"),
      };
    }
    // Plain `{ detail: "..." }` (no envelope) — preserve a safe string
    // detail, keep the stable `unknown_error` code.
    if (typeof data?.detail === "string") {
      return { code: "unknown_error", detail: safeDetailOr(data.detail, "Request failed") };
    }
    // Unknown shape → fallback
    return { code: "unknown_error", detail: "Request failed" };
  }

  // Fallback
  return { code: "unknown_error", detail: "Request failed" };
}
