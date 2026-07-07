// ─── Edge Middleware (Next.js wrapper) ────────────────────────
// Thin wrapper over the pure `decideMiddleware` logic. Keeps `next/server`
// out of the testable core so the routing rules run under bare Node.

import { NextResponse } from "next/server";
import { decideMiddleware } from "./middleware-logic.ts";

export function middleware(request: Request): NextResponse | null {
  const decision = decideMiddleware(request);
  if (decision.redirect === null) return null;
  const target = new URL(decision.redirect, new URL(request.url).origin);
  return NextResponse.redirect(target, 307);
}

export const config = {
  // Only run on the auth pages — keep the middleware scope minimal so
  // the studio + generation routes never pay the edge cost.
  matcher: ["/login", "/register", "/auth/verify"],
};