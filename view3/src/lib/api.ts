// ─── API Library Barrel ─────────────────────────────────────────
// Re-exports the shared API client components under the spec-required
// `lib/api.ts` contract:
//
//   submitGenerate(request) → POST /generate
//   getWsUrl(jobId)        → WebSocket URL for job events
//
// Consumers import from `@/lib/api` per the spec requirement.
// Implementation lives in `@/shared/infrastructure/api-client.ts`.

export {
  submitGenerate,
  getWsUrl,
  fetchImageBinary,
  normalizeError,
} from "@/shared/infrastructure/api-client";
export type { ApiError } from "@/shared/infrastructure/api-client";
