// ─── Auth Reducer ──────────────────────────────────────────────
// State machine for the AuthProvider. Status transitions:
//   idle ──mount──▶ bootstrapping ──GET /auth/me 200──▶ authenticated
//                                 └──GET /auth/me 401──▶ unauthenticated (no error UI)
//   authenticated ──logout──▶ unauthenticated
//   unauthenticated ──login success──▶ authenticated
//
// Pure reducer — no React, no IO. The provider wires effects around it.

import type { AuthSession, AuthUser } from "../domain/user.ts";

export type { AuthSession };

export type AuthAction =
  | { type: "BOOTSTRAP_START" }
  | { type: "BOOTSTRAP_SUCCESS"; user: AuthUser }
  | { type: "BOOTSTRAP_FAIL" }
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
      // Bootstrap failure (no cookie / network) → anonymous, no error UI.
      return { ...state, status: "unauthenticated", user: null, error: null };

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