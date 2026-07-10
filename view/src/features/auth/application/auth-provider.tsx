"use client";

// ─── AuthProvider ──────────────────────────────────────────────
// React context provider that bootstraps the auth state on mount
// (calls GET /auth/me) and exposes useAuth() to the rest of the app.
// State machine: idle → bootstrapping → authenticated | unauthenticated |
// bootstrap_retryable. Transient failures remain recoverable.

import React, { useCallback, useEffect, useReducer, useRef, useState, type ReactNode } from "react";
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
  verifyEmail as verifyEmailApi,
} from "../infrastructure/auth-api.ts";
import { setSessionExpiredHandler } from "../../../shared/infrastructure/api-client.ts";

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Build the /login redirect URL with the current path encoded as the
 * `next` query param. Pure function — no window/router deps — so it is
 * testable under bare Node and reusable outside React. The path is
 * `window.location.pathname + window.location.search` as captured at
 * call time by `handleSessionExpired`.
 *
 * Exported so the redirect contract (refresh failure → /login?next=...)
 * is provable at runtime, not just by source inspection.
 */
export function buildLoginRedirectUrl(currentPath: string): string {
  return `/login?next=${encodeURIComponent(currentPath)}`;
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
      window.location.href = buildLoginRedirectUrl(currentPath);
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

  const [bootstrapAttempt, setBootstrapAttempt] = useState(0);
  const [isRetrying, setIsRetrying] = useState(false);
  const bootstrapInFlight = useRef(false);

  const runBootstrap = useCallback((isRetry: boolean) => {
    let cancelled = false;
    bootstrapInFlight.current = true;
    if (isRetry) setIsRetrying(true);
    dispatch({ type: "BOOTSTRAP_START" });
    getCurrentUser()
      .then((user: AuthUser) => {
        if (!cancelled) dispatch({ type: "BOOTSTRAP_SUCCESS", user });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const isTransient =
          typeof err === "object" &&
          err !== null &&
          (err as { transient?: boolean }).transient === true;
        if (isTransient) {
          const error =
            typeof err === "object" && err !== null && "code" in err
              ? String((err as { code: unknown }).code)
              : "bootstrap_transient";
          dispatch({ type: "BOOTSTRAP_RETRYABLE", error });
          return;
        }
        dispatch({ type: "BOOTSTRAP_FAIL" });
      })
      .finally(() => {
        bootstrapInFlight.current = false;
        if (isRetry) setIsRetrying(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => runBootstrap(bootstrapAttempt > 0), [bootstrapAttempt, runBootstrap]);

  const retryBootstrap = useCallback(() => {
    if (bootstrapInFlight.current) return;
    setBootstrapAttempt((attempt) => attempt + 1);
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

  // 4R CRITICAL 2 — verifyEmail: POST /auth/verify-email, then update the
  // auth context with the verified user the backend returns. This keeps
  // the UI in sync without a second GET /auth/me round-trip. The returned
  // user's email_verified is the LIVE (post-verify) value, so the banner
  // disappears + the save gate opens immediately on success.
  const verifyEmail = async (email: string, token: string): Promise<boolean> => {
    try {
      const user = await verifyEmailApi(email, token);
      dispatch({ type: "USER_UPDATED", user });
      return true;
    } catch (err) {
      // Re-throw the structured ApiError so the VerifyEmailPage can map
      // the error code (token_expired / token_already_consumed /
      // invalid_token) to the right UI message. The provider does NOT
      // dispatch LOGIN_FAIL — the verify page owns the error display.
      throw err;
    }
  };

  const value: UseAuthValue = {
    user: state.user,
    status: state.status,
    isAuthenticated: state.status === "authenticated" && state.user !== null,
    isVerified: state.user?.email_verified === true,
    isBootstrapping: state.status === "bootstrapping" || state.status === "idle",
    isBootstrapRetryable: state.status === "bootstrap_retryable",
    isRetryingBootstrap: isRetrying,
    bootstrapError: state.status === "bootstrap_retryable" ? state.error : null,
    error: state.error,
    login,
    register,
    logout,
    logoutGlobal,
    resendVerification,
    verifyEmail,
    retryBootstrap,
    handleSessionExpired,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

// Re-export the action type for tests that exercise the reducer.
export type { AuthAction };
