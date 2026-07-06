// ─── Unit Tests: Auth Reducer ────────────────────────────────────
// Verifies the state-machine transitions for the AuthProvider reducer.

import { describe, it } from "node:test";
import assert from "node:assert";
import {
  authReducer,
  initialAuthState,
  type AuthAction,
  type AuthSession,
} from "../application/auth-reducer.ts";

void describe("authReducer", () => {
  void it("initial state is idle with no user and no error", () => {
    assert.strictEqual(initialAuthState.status, "idle");
    assert.strictEqual(initialAuthState.user, null);
    assert.strictEqual(initialAuthState.error, null);
  });

  void it("BOOTSTRAP_START transitions idle → bootstrapping", () => {
    const result = authReducer(initialAuthState, { type: "BOOTSTRAP_START" });
    assert.strictEqual(result.status, "bootstrapping");
    assert.strictEqual(result.user, null);
    assert.strictEqual(result.error, null);
  });

  void it("BOOTSTRAP_START from unauthenticated still moves to bootstrapping", () => {
    const state: AuthSession = { ...initialAuthState, status: "unauthenticated" };
    const result = authReducer(state, { type: "BOOTSTRAP_START" });
    assert.strictEqual(result.status, "bootstrapping");
  });

  void it("BOOTSTRAP_SUCCESS sets user + authenticated", () => {
    const user = { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
    const result = authReducer(initialAuthState, {
      type: "BOOTSTRAP_SUCCESS",
      user,
    });
    assert.strictEqual(result.status, "authenticated");
    assert.strictEqual(result.user?.id, "u1");
    assert.strictEqual(result.error, null);
  });

  void it("BOOTSTRAP_SUCCESS keeps email_verified=false as authenticated (unverified is still authed)", () => {
    const user = { id: "u1", email: "a@b.com", email_verified: false, created_at: "t" };
    const result = authReducer(initialAuthState, {
      type: "BOOTSTRAP_SUCCESS",
      user,
    });
    assert.strictEqual(result.status, "authenticated");
    assert.strictEqual(result.user?.email_verified, false);
  });

  void it("BOOTSTRAP_FAIL transitions to unauthenticated with no error UI (network fails → anon)", () => {
    const state: AuthSession = { ...initialAuthState, status: "bootstrapping" };
    const result = authReducer(state, { type: "BOOTSTRAP_FAIL" });
    assert.strictEqual(result.status, "unauthenticated");
    assert.strictEqual(result.user, null);
    assert.strictEqual(result.error, null);
  });

  void it("LOGIN_START transitions to bootstrapping (in-flight login)", () => {
    const state: AuthSession = { ...initialAuthState, status: "unauthenticated" };
    const result = authReducer(state, { type: "LOGIN_START" });
    assert.strictEqual(result.status, "bootstrapping");
    assert.strictEqual(result.error, null);
  });

  void it("LOGIN_SUCCESS sets user + authenticated + clears error", () => {
    const state: AuthSession = {
      ...initialAuthState,
      status: "bootstrapping",
      error: "old",
    };
    const user = { id: "u2", email: "a@b.com", email_verified: true, created_at: "t" };
    const result = authReducer(state, { type: "LOGIN_SUCCESS", user });
    assert.strictEqual(result.status, "authenticated");
    assert.strictEqual(result.user?.id, "u2");
    assert.strictEqual(result.error, null);
  });

  void it("LOGIN_FAIL sets error + unauthenticated", () => {
    const state: AuthSession = { ...initialAuthState, status: "bootstrapping" };
    const result = authReducer(state, {
      type: "LOGIN_FAIL",
      error: "invalid_credentials",
    });
    assert.strictEqual(result.status, "unauthenticated");
    assert.strictEqual(result.user, null);
    assert.strictEqual(result.error, "invalid_credentials");
  });

  void it("LOGOUT transitions authenticated → unauthenticated, clears user", () => {
    const state: AuthSession = {
      ...initialAuthState,
      status: "authenticated",
      user: { id: "u3", email: "a@b.com", email_verified: true, created_at: "t" },
    };
    const result = authReducer(state, { type: "LOGOUT" });
    assert.strictEqual(result.status, "unauthenticated");
    assert.strictEqual(result.user, null);
    assert.strictEqual(result.error, null);
  });

  void it("USER_UPDATED refreshes the user while keeping authenticated (e.g. after verify-email)", () => {
    const state: AuthSession = {
      ...initialAuthState,
      status: "authenticated",
      user: { id: "u4", email: "a@b.com", email_verified: false, created_at: "t" },
    };
    const updated = { id: "u4", email: "a@b.com", email_verified: true, created_at: "t" };
    const result = authReducer(state, { type: "USER_UPDATED", user: updated });
    assert.strictEqual(result.status, "authenticated");
    assert.strictEqual(result.user?.email_verified, true);
  });

  void it("SET_ERROR sets the error string without changing auth status", () => {
    const state: AuthSession = { ...initialAuthState, status: "unauthenticated" };
    const result = authReducer(state, { type: "SET_ERROR", error: "resend failed" });
    assert.strictEqual(result.error, "resend failed");
    assert.strictEqual(result.status, "unauthenticated");
  });

  void it("SET_ERROR with null clears the error", () => {
    const state: AuthSession = { ...initialAuthState, status: "unauthenticated", error: "x" };
    const result = authReducer(state, { type: "SET_ERROR", error: null });
    assert.strictEqual(result.error, null);
  });

  void it("unknown action returns state unchanged", () => {
    const result = authReducer(initialAuthState, { type: "UNKNOWN" } as unknown as AuthAction);
    assert.strictEqual(result, initialAuthState);
  });
});