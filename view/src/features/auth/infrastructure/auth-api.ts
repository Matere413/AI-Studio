// ─── Auth API client ───────────────────────────────────────────
// Thin wrapper over the backend /auth/* endpoints. Every call goes
// through `fetchWithSession` (so the anonymous X-Session-ID header
// path stays intact) and explicitly sets `credentials: "include"` so
// the cross-origin Modal backend receives the auth cookies.
//
// Cookie names are read-only here — the backend owns Set-Cookie. We
// only surface the constants via the domain module for middleware/tests.

import { fetchWithSession, markSessionActive } from "../../../shared/infrastructure/api-client.ts";
import { env } from "../../../shared/infrastructure/env.ts";
import type { ApiError } from "../../../shared/infrastructure/api-client.ts";
import type { AuthUser } from "../domain/user.ts";

// ─── Error handling ────────────────────────────────────────────

async function throwOnError(res: Response): Promise<never> {
  let code = "unknown_error";
  let detail = `Request failed with status ${res.status}`;
  const status = res.status;
  try {
    const body = (await res.json()) as Record<string, unknown>;
    const error = body?.error as Record<string, unknown> | undefined;
    if (error && typeof error.code === "string") {
      code = error.code;
      detail = typeof error.detail === "string" ? error.detail : detail;
    }
  } catch {
    // Body not JSON — keep defaults
  }
  throw { code, detail, status } satisfies ApiError & { status: number };
}

export interface BootstrapError {
  code: string;
  detail: string;
  transient: boolean;
}

function classifyBootstrapError(err: unknown): BootstrapError {
  const value = typeof err === "object" && err !== null ? err as Record<string, unknown> : {};
  const code = typeof value.code === "string" ? value.code : "unknown_error";
  const detail = typeof value.detail === "string" ? value.detail : "Bootstrap failed";
  const status = typeof value.status === "number" ? value.status : 0;
  return {
    code,
    detail,
    transient: code === "client_error" || code === "timeout" || status === 429 || status >= 500,
  };
}

/**
 * Perform a JSON request to an auth endpoint and return the parsed body.
 * Forces `credentials: "include"` so cross-origin cookies flow.
 * Throws `ApiError` on network failure or non-ok HTTP status.
 */
async function authRequest<T>(
  path: string,
  method: "GET" | "POST",
  body?: Record<string, unknown>,
  skipAuthRefresh = false,
  signal?: AbortSignal,
): Promise<T> {
  const opts: Record<string, unknown> = {
    method,
    credentials: "include",
    skipAuthRefresh,
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  if (signal) opts.signal = signal;
  const res = await fetchWithSession(
    `${env.apiBaseUrl}${path}`,
    opts as Parameters<typeof fetchWithSession>[1],
  );
  if (!res.ok) {
    await throwOnError(res);
  }
  return res.json() as Promise<T>;
}

// ─── Response shapes ───────────────────────────────────────────

interface AuthUserResponse {
  user?: AuthUser;
}

interface MeResponse extends AuthUser {}

// ─── API functions ─────────────────────────────────────────────

/** POST /auth/register — returns the created user (cookies set by backend). */
export async function registerUser(email: string, password: string): Promise<AuthUser> {
  const body = await authRequest<AuthUserResponse>("/auth/register", "POST", {
    email,
    password,
  });
  if (!body.user) throw { code: "unknown_error", detail: "Missing user in register response" } satisfies ApiError;
  markSessionActive();
  return body.user;
}

/** POST /auth/login — returns the logged-in user (cookies set by backend). */
export async function loginUser(email: string, password: string): Promise<AuthUser> {
  const body = await authRequest<AuthUserResponse>("/auth/login", "POST", {
    email,
    password,
  });
  if (!body.user) throw { code: "unknown_error", detail: "Missing user in login response" } satisfies ApiError;
  markSessionActive();
  return body.user;
}

/** POST /auth/logout — revokes the current refresh token, clears cookies. */
export async function logoutUser(): Promise<void> {
  await authRequest<void>("/auth/logout", "POST");
}

/** POST /auth/logout-all — revokes every non-expired refresh token. */
export async function logoutAllUser(): Promise<void> {
  await authRequest<void>("/auth/logout-all", "POST");
}

/** POST /auth/refresh — rotates tokens, returns the user. */
export async function refreshTokens(signal?: AbortSignal): Promise<AuthUser> {
  const body = await authRequest<AuthUserResponse>("/auth/refresh", "POST", undefined, false, signal);
  if (!body.user) throw { code: "unknown_error", detail: "Missing user in refresh response" } satisfies ApiError;
  markSessionActive();
  return body.user;
}

/** POST /auth/verify-email — verifies a token, returns the verified user. */
export async function verifyEmail(email: string, token: string): Promise<AuthUser> {
  const body = await authRequest<AuthUserResponse>("/auth/verify-email", "POST", {
    email,
    token,
  });
  if (!body.user) throw { code: "unknown_error", detail: "Missing user in verify response" } satisfies ApiError;
  markSessionActive();
  return body.user;
}

/** POST /auth/resend-verification — mints a fresh 24h verification token. */
export async function resendVerification(): Promise<void> {
  await authRequest<void>("/auth/resend-verification", "POST");
}

/** GET /auth/me — hydrates bootstrap with one explicit refresh recovery. */
export async function getCurrentUser(signal?: AbortSignal): Promise<AuthUser> {
  try {
    const user = await authRequest<MeResponse>("/auth/me", "GET", undefined, true, signal);
    markSessionActive();
    return user;
  } catch (err) {
    const status = typeof err === "object" && err !== null && "status" in err
      ? (err as { status?: unknown }).status
      : undefined;
    if (status !== 401) throw classifyBootstrapError(err);
    try {
      return await refreshTokens(signal);
    } catch (refreshErr) {
      throw classifyBootstrapError(refreshErr);
    }
  }
}
