// ─── Auth Domain Types ─────────────────────────────────────────
// Pure domain types for the auth feature. No React, no fetch, no IO.
// Imported by the application (AuthProvider, useAuth) and infrastructure
// (auth-api) layers. Cookie names are read-only constants in the frontend
// (set by the backend via Set-Cookie); surfaced here for middleware + tests.

export const AUTH_COOKIE_NAME = "ai-studio-auth";
export const REFRESH_COOKIE_NAME = "ai-studio-refresh";

// ─── User ──────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  email_verified: boolean;
  /** ISO 8601 timestamp of registration. */
  created_at: string;
}

// ─── Auth Status (reducer state machine) ───────────────────────

export type AuthStatus =
  | "idle"
  | "bootstrapping"
  | "authenticated"
  | "unauthenticated"
  | "error";

// ─── Auth Session ──────────────────────────────────────────────

export interface AuthSession {
  /** The authenticated user, or null when anonymous / bootstrapping. */
  user: AuthUser | null;
  status: AuthStatus;
  /** Surfaced when status === "error" (non-bootstrap network failures). */
  error: string | null;
}

// ─── Initial State ─────────────────────────────────────────────

export const initialAuthState: AuthSession = {
  user: null,
  status: "idle",
  error: null,
};