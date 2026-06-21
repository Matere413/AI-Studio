// ─── Infrastructure Barrel ────────────────────────────────────
// Re-exports shared infrastructure for the hexagonal shell.

export { env } from "./env";
export {
  submitGenerate,
  getWsUrl,
  fetchImageBinary,
  normalizeError,
} from "./api-client";
export type { ApiError } from "./api-client";
