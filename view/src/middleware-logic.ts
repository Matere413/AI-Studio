// ─── Middleware logic (pure, no Next.js runtime dependency) ─────
// Extracted so the routing rules are testable under bare Node without
// importing `next/server`. The thin `middleware.ts` wrapper turns the
// decision into a `NextResponse.redirect`.
//
// Rules (per generative-ai-studio-frontend spec "Route Guard Middleware"):
//   - Authed user on /login or /register → redirect to /studio
//   - /auth/verify ALWAYS passes through (both anon and authed) so the
//     verify page can render and consume the `email` + `token` params.
//     A newly registered user may still carry auth cookies when they
//     open the verification email link; blocking them would prevent
//     email verification from ever completing.
//   - Any visitor (anon or authed) on the studio (/studio) or landing (/)
//     → pass through (the matcher does not cover them)
//
// Cookie presence only — NO JWT verification at the edge.

import { AUTH_COOKIE_NAME } from "./features/auth/domain/user.ts";

export interface MiddlewareDecision {
  /** Absolute path to redirect to, or null to pass through. */
  redirect: string | null;
}

function hasAuthCookie(request: Request): boolean {
  const header = request.headers.get("cookie");
  if (!header) return false;
  const target = `${AUTH_COOKIE_NAME}=`;
  return header
    .split(";")
    .map((p) => p.trim())
    .some((p) => p.startsWith(target) && p.length > target.length);
}

export function decideMiddleware(request: Request): MiddlewareDecision {
  const url = new URL(request.url);
  const { pathname } = url;
  const authed = hasAuthCookie(request);

  // Authed users on the auth-entry pages are sent to the studio. /auth/verify
  // is deliberately excluded: the verify page MUST render for both anon and
  // authed visitors so it can read the `email` + `token` query params and call
  // POST /auth/verify-email. An authenticated-but-unverified user still needs
  // to reach this page (they carry cookies from registration).
  if (authed && (pathname === "/login" || pathname === "/register")) {
    return { redirect: "/studio" };
  }
  return { redirect: null };
}