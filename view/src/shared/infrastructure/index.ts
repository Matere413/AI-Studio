// ─── Infrastructure Barrel ────────────────────────────────────
// Re-exports shared infrastructure for the hexagonal shell.

export { env } from "./env";
export {
  submitGenerate,
  submitOrchestrate,
  getWsUrl,
  fetchImageBinary,
  normalizeError,
} from "./api-client";
export type { ApiError } from "./api-client";
export {
  emitTelemetry,
  setTelemetrySink,
  clearTelemetryDedup,
  createBackendSink,
  buildTelemetryEndpoint,
} from "./telemetry";
export type { TelemetryEvent, TelemetryLevel, TelemetrySink } from "./telemetry";
