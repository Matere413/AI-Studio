// ─── Session Utilities ─────────────────────────────────────────
// Shared helpers for session cookie handling across API routes
// and client code.  Centralized to avoid duplicating cookie-name
// constants and decode logic across route handlers.
//
// Route handlers read the cookie from the `Request` header directly
// instead of importing `next/headers`.  This keeps tests runnable
// under bare Node (no Next.js runtime dependency) and avoids coupling
// to the Next.js runtime for what is fundamentally a simple cookie read.

export const SESSION_COOKIE_NAME = "ai-studio-session-id";

/**
 * Read the session cookie from a `Request`'s `Cookie` header.
 *
 * Returns `null` when the cookie is missing, empty, or its value
 * fails URI-decode (malformed).
 *
 * This is a replacement for `next/headers` `cookies()` that works
 * in any runtime (Next.js server, Node tests, edge workers).
 */
export function readSessionCookie(request: Request): string | null {
  const cookieHeader = request.headers.get("cookie");
  if (!cookieHeader) return null;

  for (const part of cookieHeader.split(";")) {
    const trimmed = part.trim();
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    const name = trimmed.slice(0, idx).trim();
    if (name === SESSION_COOKIE_NAME) {
      const raw = trimmed.slice(idx + 1);
      if (!raw) return null;
      try {
        return decodeURIComponent(raw);
      } catch {
        // Malformed percent-encoding — reject (cookie value is unusable)
        return null;
      }
    }
  }
  return null;
}
