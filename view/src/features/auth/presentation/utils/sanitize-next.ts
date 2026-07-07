// ─── sanitizeNext (open-redirect guard) ───────────────────────
// Used by LoginForm and RegisterForm on success to compute the
// destination from the `next` query param, falling back to /studio.
// Accepts only same-origin `/`-prefixed paths; rejects protocol-
// relative (`//evil.com`), scheme injection (any `:`), and non-`/`
// input. Returns null when the input is unsafe or absent.

export function sanitizeNext(next: string | null | undefined): string | null {
  if (!next) return null;
  if (!next.startsWith("/")) return null;        // same-origin only
  if (next.startsWith("//")) return null;        // block protocol-relative
  if (next.includes(":")) return null;           // block javascript:, data:, etc.
  return next;
}