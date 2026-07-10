// ─── useAuth hook ───────────────────────────────────────────────
// Reads the auth context exposed by AuthProvider. Throws when used
// outside a provider so wiring mistakes fail loudly.

import { useContext } from "react";
import { AuthContext } from "./auth-context.ts";
import type { AuthUser } from "../domain/user.ts";

export interface UseAuthValue {
  user: AuthUser | null;
  status: "idle" | "bootstrapping" | "authenticated" | "unauthenticated" | "bootstrap_retryable" | "error";
  isAuthenticated: boolean;
  isVerified: boolean;
  isBootstrapping: boolean;
  /**
   * True when a bootstrap retry is currently in flight (a `retryBootstrap()`
   * call kicked off a new `/auth/me` + optional `/auth/refresh` attempt that
   * has not yet settled). The UI SHOULD use this to disable the retry
   * affordance so a user cannot fire overlapping retries that spawn
   * duplicate `/auth/me` / `/auth/refresh` calls. Distinct from
   * `isBootstrapping` (which is true for the INITIAL mount bootstrap AND any
   * retry) so the UI can show "retrying…" while a retry is specifically
   * running. The retry path is bounded: `retryBootstrap()` is a no-op while
   * an attempt is already in flight.
   */
  isRetryingBootstrap: boolean;
  /**
   * True when the bootstrap landed in a TRANSIENT failure state
   * (`status === "bootstrap_retryable"`). A transient failure (5xx / 429 /
   * network / timeout on /auth/me or /auth/refresh) does NOT prove the
   * session is dead — the refresh cookie may still be valid and a bounded
   * `retryBootstrap()` can recover it. The UI should render a recoverable
   * state (retry button) instead of an anonymous shell so a transient
   * backend hiccup does not falsely log the user out.
   */
  isBootstrapRetryable: boolean;
  /**
   * The error code surfaced when `status === "bootstrap_retryable"`, else
   * null. Drives the retry affordance copy (e.g. "network" / "timeout").
   */
  bootstrapError: string | null;
  error: string | null;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  logoutGlobal: () => Promise<void>;
  resendVerification: () => Promise<boolean>;
  /**
   * 4R CRITICAL 2 — POST /auth/verify-email and update the auth context
   * with the verified user. Returns true on success, throws a structured
   * ApiError ({code, detail}) on failure so the caller can map the error
   * code (token_expired / token_already_consumed / invalid_token).
   */
  verifyEmail: (email: string, token: string) => Promise<boolean>;
  /**
   * Bounded retry of the bootstrap. Called by the UI when the bootstrap
   * landed in `bootstrap_retryable` (transient failure). Re-runs the
   * bootstrap effect exactly once (no retry storm). A retry while an
   * attempt is already in flight is a NO-OP — the in-flight attempt will
   * resolve and dispatch, so an overlapping retry would only create
   * duplicate `/auth/me` / `/auth/refresh` calls. While in flight,
   * `isRetryingBootstrap` is true so the UI can disable its retry control.
   * On success the state flips to authenticated; on a second transient
   * failure it stays in `bootstrap_retryable` so the user can retry again;
   * on a definitive failure it flips to unauthenticated.
   */
  retryBootstrap: () => void;
  /**
   * Clear auth state + redirect to /login?next=<currentPath>. Called
   * automatically by the api-client when a refresh-on-401 fails; also
   * exposed so components can trigger it directly (e.g. on a manual 401).
   */
  handleSessionExpired: () => void;
}

export function useAuth(): UseAuthValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth MUST be used inside an <AuthProvider>");
  }
  return ctx;
}