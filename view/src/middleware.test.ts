// ─── Unit Tests: edge middleware routing ───────────────────────
// Verifies cookie-presence routing rules (spec: Route Guard Middleware):
//   - Authed user on /login or /register → redirect to /studio
//   - /auth/verify ALWAYS passes through (authed AND anonymous) so the
//     verify page can render and consume the `email` + `token` params.
//     A newly registered user may carry auth cookies when opening the
//     verification link; blocking them would prevent verification.
//   - Any visitor (anon or authed) on the studio (/studio or /) → pass through
// Cookie presence only — NO JWT verification at the edge.

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
  void it("authed user visiting /login is redirected to /studio", () => {
    const req = buildRequest("/login", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, "/studio", "MUST redirect authed /login to /studio");
  });

  void it("authed user visiting /register is redirected to /studio", () => {
    const req = buildRequest("/register", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, "/studio", "MUST redirect authed /register to /studio");
  });

  void it("authed user visiting /auth/verify passes through (page must render to consume token)", () => {
    const req = buildRequest("/auth/verify?token=x&email=y", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed /auth/verify — the verify page must render to consume email + token params");
  });

  void it("authed user visiting /auth/verify without params still passes through (page renders its own missing-param error)", () => {
    const req = buildRequest("/auth/verify", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed /auth/verify even without params — the page handles missing params itself");
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

  void it("anonymous user visiting /auth/verify passes through (token link clicked before login)", () => {
    const req = buildRequest("/auth/verify?token=x&email=y");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /auth/verify");
  });

  void it("authed user visiting the studio (/studio) passes through", () => {
    const req = buildRequest("/studio", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed /studio");
  });

  void it("anonymous user visiting /studio passes through (generation stays public)", () => {
    const req = buildRequest("/studio");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /studio — generation stays public");
  });

  void it("authed user visiting the landing (/) passes through (no forced redirect)", () => {
    const req = buildRequest("/", { authCookie: "fake-jwt" });
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect authed / — landing renders for all visitors");
  });

  void it("anonymous user visiting the landing (/) passes through", () => {
    const req = buildRequest("/");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous / — landing is public");
  });

  void it("anonymous user visiting /projects passes through (save gate handled client-side + backend 401)", () => {
    const req = buildRequest("/projects");
    const decision = decideMiddleware(req);
    assert.strictEqual(decision.redirect, null, "MUST NOT redirect anonymous /projects — the backend 401 + client SaveCTA handle gating");
  });
});