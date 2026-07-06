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
}

export function useAuth(): UseAuthValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth MUST be used inside an <AuthProvider>");
  }
  return ctx;
}