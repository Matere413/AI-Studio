// ─── Auth Reducer ──────────────────────────────────────────────
// State machine for the AuthProvider. Status transitions:
//   idle ──mount──▶ bootstrapping ──GET /auth/me 200──▶ authenticated
//                                 └──GET /auth/me 401 + refresh 401/403──▶ unauthenticated (definitive)
//                                 └──GET /auth/me 401 + refresh 5xx/429/network──▶ bootstrap_retryable (transient)
//                                 └──GET /auth/me 5xx/429/network──▶ bootstrap_retryable (transient)
//   authenticated ──logout──▶ unauthenticated
//   unauthenticated ──login success──▶ authenticated
//   bootstrap_retryable ──retryBootstrap──▶ bootstrapping (bounded retry, no storm)
//
// Pure reducer — no React, no IO. The provider wires effects around it.
//
// Transient vs definitive bootstrap failures (production blocker):
//   A transient refresh failure (5xx / 429 / network / timeout) does NOT
//   prove the session is dead — the refresh cookie may still be valid and
//   a later retry could recover it. Marking the user anonymous on a
//   transient failure would falsely log them out. The
//   ``bootstrap_retryable`` state surfaces a recoverable UX (retry button)
//   instead of an anonymous shell, and a bounded ``retryBootstrap()``
//   re-runs the bootstrap ONCE per user action (no retry storm). Only
//   definitive auth failures (401/403 on refresh, or a non-401 /auth/me
//   that is not a transient error) land on ``unauthenticated``.

import type { AuthSession, AuthUser } from "../domain/user.ts";

export type { AuthSession };

export type AuthAction =
  | { type: "BOOTSTRAP_START" }
  | { type: "BOOTSTRAP_SUCCESS"; user: AuthUser }
  | { type: "BOOTSTRAP_FAIL" }
  | { type: "BOOTSTRAP_RETRYABLE"; error: string }
  | { type: "LOGIN_START" }
  | { type: "LOGIN_SUCCESS"; user: AuthUser }
  | { type: "LOGIN_FAIL"; error: string }
  | { type: "LOGOUT" }
  | { type: "USER_UPDATED"; user: AuthUser }
  | { type: "SET_ERROR"; error: string | null };

export { initialAuthState } from "../domain/user.ts";

export function authReducer(state: AuthSession, action: AuthAction): AuthSession {
  switch (action.type) {
    case "BOOTSTRAP_START":
      return { ...state, status: "bootstrapping", error: null };

    case "BOOTSTRAP_SUCCESS":
      return { ...state, status: "authenticated", user: action.user, error: null };

    case "BOOTSTRAP_FAIL":
      // Definitive bootstrap failure (no cookie / 401+refresh 401/403) →
      // anonymous, no error UI.
      return { ...state, status: "unauthenticated", user: null, error: null };

    case "BOOTSTRAP_RETRYABLE":
      // Transient bootstrap failure (5xx / 429 / network / timeout on
      // /auth/me or /auth/refresh) → recoverable state, NOT anonymous. The
      // session may still be valid; a bounded retry can recover it. The
      // error code is surfaced so the UI can show a retry affordance.
      return {
        ...state,
        status: "bootstrap_retryable",
        user: null,
        error: action.error,
      };

    case "LOGIN_START":
      return { ...state, status: "bootstrapping", error: null };

    case "LOGIN_SUCCESS":
      return { ...state, status: "authenticated", user: action.user, error: null };

    case "LOGIN_FAIL":
      return { ...state, status: "unauthenticated", user: null, error: action.error };

    case "LOGOUT":
      return { ...state, status: "unauthenticated", user: null, error: null };

    case "USER_UPDATED":
      return { ...state, user: action.user };

    case "SET_ERROR":
      return { ...state, error: action.error };

    default:
      return state;
  }
}