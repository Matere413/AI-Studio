// ─── useAuth hook ───────────────────────────────────────────────
// Reads the auth context exposed by AuthProvider. Throws when used
// outside a provider so wiring mistakes fail loudly.

import { useContext } from "react";
import { AuthContext } from "./auth-context.ts";
import type { AuthUser } from "../domain/user.ts";

export interface UseAuthValue {
  user: AuthUser | null;
  status: "idle" | "bootstrapping" | "authenticated" | "unauthenticated" | "error";
  isAuthenticated: boolean;
  isVerified: boolean;
  isBootstrapping: boolean;
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