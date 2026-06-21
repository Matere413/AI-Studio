// ─── Environment Configuration ────────────────────────────────
// Reads runtime env vars and derives URLs.
// Use `env.apiBaseUrl` / `env.wsBaseUrl` after ensuring
// NEXT_PUBLIC_API_BASE_URL is set in .env.local.

function readApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not defined. " +
        "Set it in .env.local or your deployment environment.",
    );
  }
  // Strip trailing slash for consistent URL joining
  return url.replace(/\/+$/, "");
}

export const env = Object.freeze({
  get apiBaseUrl(): string {
    return readApiBaseUrl();
  },
  /** Derives WebSocket URL: https → wss, http → ws */
  get wsBaseUrl(): string {
    return readApiBaseUrl().replace(/^http/, "ws");
  },
});
