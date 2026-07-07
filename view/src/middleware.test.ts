// ─── Unit Tests: edge middleware routing ───────────────────────
// Verifies cookie-presence routing rules:
//   - Authed user on /login or /register → redirect to /
//   - Anonymous user on /login or /register → pass through (page renders)
//   - Any visitor (anon or authed) on the studio → pass through
//   - /verify-email → always pass through (token link may be clicked before login)
// No JWT verification at the edge.

import { describe, it } from "node:test";
import assert from "node:assert";
import { AUTH_COOKIE_NAME } from "../src/features/auth/domain/user.ts";
import { decideMiddleware } from "../src/middleware-logic.ts";

function buildRequest(
  path: string,
  opts: { authCookie?: string; method?: string } = {},
): Request {
  const url = `https://studio.example.com${path}`;
  const headers: Record<string, string> = {};
  if (opts.authCookie !== undefined) {
    headers.cookie = `${AUTH_COOKIE_NAME}=${opts.authCookie}`;
  }
  return new Request(url, { method: opts.method ?? "GET", headers });
}

void describe("middleware routing", () => {
  void it("authed user visiting /login is redirected to /", () => {
    const req = buildRequest("/login", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, "/", "MUST redirect authed /login to /");
  });

  void it("authed user visiting /register is redirected to /", () => {
    const req = buildRequest("/register", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, "/");
  });

  void it("anonymous user visiting /login passes through (page renders)", () => {
    const req = buildRequest("/login");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /login");
  });

  void it("anonymous user visiting /register passes through", () => {
    const req = buildRequest("/register");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /register");
  });

  void it("authed user visiting the studio (/) passes through", () => {
    const req = buildRequest("/", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed studio");
  });

  void it("anonymous user visiting the studio (/) passes through (generation works)", () => {
    const req = buildRequest("/");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous studio — generation stays public");
  });

  void it("anonymous user visiting /verify-email passes through (token link clicked before login)", () => {
    const req = buildRequest("/auth/verify?token=x&email=y");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous verify-email");
  });

  void it("authed user visiting /verify-email passes through", () => {
    const req = buildRequest("/auth/verify?token=x&email=y", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed verify-email");
  });

  void it("anonymous user visiting /projects passes through (save gate handled client-side + backend 401)", () => {
    const req = buildRequest("/projects");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /projects — the backend 401 + client SaveCTA handle gating");
  });
});