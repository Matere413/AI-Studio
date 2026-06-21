// ─── Chat Infrastructure Layer Barrel ─────────────────────────
// Re-exports shared infrastructure for the chat feature.

export { env } from "@/shared/infrastructure/env";
export {
  submitGenerate,
  getWsUrl,
  fetchImageBinary,
  normalizeError,
} from "@/shared/infrastructure/api-client";
export type { ApiError } from "@/shared/infrastructure/api-client";
