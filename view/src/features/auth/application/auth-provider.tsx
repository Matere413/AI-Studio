"use client";

// ─── AuthProvider ──────────────────────────────────────────────
// React context provider that bootstraps the auth state on mount
// (calls GET /auth/me) and exposes useAuth() to the rest of the app.
// State machine: idle → bootstrapping → authenticated | unauthenticated.
// Bootstrap failure (no cookie / network) → anonymous, no error UI.

import React, { useEffect, useReducer, type ReactNode } from "react";
import { authReducer, initialAuthState } from "./auth-reducer.ts";
import type { AuthAction } from "./auth-reducer.ts";
import { AuthContext } from "./auth-context.ts";
import type { AuthUser } from "../domain/user.ts";
import type { UseAuthValue } from "./use-auth.ts";
import {
  getCurrentUser,
  loginUser,
  registerUser,
  logoutUser,
  logoutAllUser,
  resendVerification as resendVerificationApi,
} from "../infrastructure/auth-api.ts";
import { setSessionExpiredHandler } from "../../../shared/infrastructure/api-client.ts";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, initialAuthState);

  // Slice 4 — handleSessionExpired: clears auth state + redirects to
  // /login?next=<current-path>. Registered with the api-client so a
  // refresh-on-401 failure transparently logs the user out. Defined inside
  // the provider so it closes over `dispatch`; registered once on mount.
  const handleSessionExpired = () => {
    dispatch({ type: "LOGOUT" });
    // Redirect to /login with the current path as the `next` query param so
    // the user lands back where they were after re-authenticating. In a
    // bare-Node test (no window), this is a no-op.
    if (typeof window !== "undefined" && typeof window.location !== "undefined") {
      const currentPath = window.location.pathname + window.location.search;
      window.location.href = `/login?next=${encodeURIComponent(currentPath)}`;
    }
  };

  // Register the session-expired handler on mount + clear it on unmount.
  // The api-client calls this when a refresh-on-401 fails (refresh token
  // also dead) — the wrapper stays free of React/router imports.
  useEffect(() => {
    setSessionExpiredHandler(handleSessionExpired);
    return () => {
      setSessionExpiredHandler(null);
    };
  }, []);

  // Bootstrap on mount — hydrate user state from the access cookie.
  useEffect(() => {
    let cancelled = false;
    dispatch({ type: "BOOTSTRAP_START" });
    getCurrentUser()
      .then((user: AuthUser) => {
        if (!cancelled) dispatch({ type: "BOOTSTRAP_SUCCESS", user });
      })
      .catch(() => {
        // No cookie / invalid token / network failure → anonymous (no error UI).
        if (!cancelled) dispatch({ type: "BOOTSTRAP_FAIL" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    dispatch({ type: "LOGIN_START" });
    try {
      const user = await loginUser(email, password);
      dispatch({ type: "LOGIN_SUCCESS", user });
      return true;
    } catch (err) {
      const code = (err as { code?: string })?.code ?? "invalid_credentials";
      dispatch({ type: "LOGIN_FAIL", error: code });
      return false;
    }
  };

  const register = async (email: string, password: string): Promise<boolean> => {
    dispatch({ type: "LOGIN_START" });
    try {
      await registerUser(email, password);
      // Registration issues cookies but the user is unverified; do not flip
      // to authenticated here — the page redirects to "check your email".
      // Clear the bootstrapping flag back to unauthenticated.
      dispatch({ type: "BOOTSTRAP_FAIL" });
      return true;
    } catch (err) {
      const code = (err as { code?: string })?.code ?? "weak_password";
      dispatch({ type: "LOGIN_FAIL", error: code });
      return false;
    }
  };

  const logout = async (): Promise<void> => {
    try {
      await logoutUser();
    } finally {
      dispatch({ type: "LOGOUT" });
    }
  };

  const logoutGlobal = async (): Promise<void> => {
    try {
      await logoutAllUser();
    } finally {
      dispatch({ type: "LOGOUT" });
    }
  };

  const resendVerification = async (): Promise<boolean> => {
    try {
      await resendVerificationApi();
      dispatch({ type: "SET_ERROR", error: null });
      return true;
    } catch (err) {
      const code = (err as { code?: string })?.code ?? "unknown_error";
      dispatch({ type: "SET_ERROR", error: code });
      return false;
    }
  };

  const value: UseAuthValue = {
    user: state.user,
    status: state.status,
    isAuthenticated: state.status === "authenticated" && state.user !== null,
    isVerified: state.user?.email_verified === true,
    isBootstrapping: state.status === "bootstrapping" || state.status === "idle",
    error: state.error,
    login,
    register,
    logout,
    logoutGlobal,
    resendVerification,
    handleSessionExpired,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

// Re-export the action type for tests that exercise the reducer.
export type { AuthAction };