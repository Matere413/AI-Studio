// ─── Unit Tests: Auth Domain Types ──────────────────────────────
// Verifies the shape of the User, AuthSession, and AuthStatus types
// and the initial-auth-state helper used by the reducer.

import { describe, it } from "node:test";
import assert from "node:assert";
import {
  AUTH_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  initialAuthState,
  type AuthSession,
  type AuthStatus,
  type AuthUser,
} from "./user.ts";

void describe("auth domain types", () => {
  void it("AUTH_COOKIE_NAME is hyphenated ai-studio-auth", () => {
    assert.strictEqual(AUTH_COOKIE_NAME, "ai-studio-auth");
  });

  void it("REFRESH_COOKIE_NAME is hyphenated ai-studio-refresh", () => {
    assert.strictEqual(REFRESH_COOKIE_NAME, "ai-studio-refresh");
  });

  void it("AuthUser has id, email, email_verified, created_at", () => {
    const user: AuthUser = {
      id: "u1",
      email: "a@b.com",
      email_verified: false,
      created_at: "2026-01-01T00:00:00Z",
    };
    assert.strictEqual(user.id, "u1");
    assert.strictEqual(user.email, "a@b.com");
    assert.strictEqual(user.email_verified, false);
    assert.strictEqual(user.created_at, "2026-01-01T00:00:00Z");
  });

  void it("AuthStatus union includes all five states", () => {
    const states: AuthStatus[] = [
      "idle",
      "bootstrapping",
      "authenticated",
      "unauthenticated",
      "error",
    ];
    assert.deepStrictEqual(states, [
      "idle",
      "bootstrapping",
      "authenticated",
      "unauthenticated",
      "error",
    ]);
  });

  void it("AuthSession combines user + status", () => {
    const session: AuthSession = {
      user: { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" },
      status: "authenticated",
    };
    assert.strictEqual(session.status, "authenticated");
    assert.strictEqual(session.user?.id, "u1");
  });

  void it("initialAuthState is idle with no user", () => {
    assert.strictEqual(initialAuthState.status, "idle");
    assert.strictEqual(initialAuthState.user, null);
    assert.strictEqual(initialAuthState.error, null);
  });
});