// ─── Middleware logic (pure, no Next.js runtime dependency) ─────
// Extracted so the routing rules are testable under bare Node without
// importing `next/server`. The thin `middleware.ts` wrapper turns the
// decision into a `NextResponse.redirect`.
//
// Rules (per frontend spec):
//   - Authed user on /login or /register → redirect to /
//   - Anonymous user on /login or /register → pass through (page renders)
//   - Any visitor (anon or authed) on the studio → pass through
//   - /verify-email → always pass through (token link may be clicked before login)
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

  if (authed && (pathname === "/login" || pathname === "/register")) {
    return { redirect: "/" };
  }
  return { redirect: null };
}