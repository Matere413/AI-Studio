// Dependency-free telemetry seam. Events are safe, best-effort, and never throw.

export type TelemetryLevel = "info" | "warn" | "error";
export type TelemetryFields = Record<string, string | number | boolean | null>;

export interface TelemetryEvent {
  name: string;
  fields: TelemetryFields;
  level: TelemetryLevel;
  timestamp: number;
}

export type TelemetrySink = (event: TelemetryEvent) => void;

let sink: TelemetrySink | null = null;
const consoleWarnedFor = new Set<string>();
const SENSITIVE_KEY_FRAGMENTS = [
  "token", "cookie", "password", "secret", "api_key", "apikey",
  "authorization", "credential", "session", "refresh", "header", "body", "url", "email",
];
const SAFE_KEY_EXCEPTIONS = new Set(["token_prefix"]);
const TELEMETRY_EVENTS_PATH = "/telemetry/events";
const BACKEND_SINK_TIMEOUT_MS = 8_000;

/** Register one collection sink; null restores the console fallback. */
export function setTelemetrySink(nextSink: TelemetrySink | null): void {
  sink = nextSink;
}

/** Test-only accessor. */
export function _getTelemetrySink(): TelemetrySink | null {
  return sink;
}

/** Allow a recovered event to warn again. */
export function clearTelemetryDedup(name?: string): void {
  if (name === undefined) consoleWarnedFor.clear();
  else consoleWarnedFor.delete(name);
}

/** Emit an event without allowing telemetry failures to affect the caller. */
export function emitTelemetry(
  name: string,
  fields: TelemetryFields = {},
  level: TelemetryLevel = "info",
): void {
  const event = { name: safeName(name), fields: redactSensitive(fields), level, timestamp: Date.now() };
  let sinkFailed = false;
  if (sink !== null) {
    try {
      sink(event);
    } catch {
      sinkFailed = true;
    }
  }
  if ((sink === null || sinkFailed) && !consoleWarnedFor.has(event.name)) {
    consoleWarnedFor.add(event.name);
    // eslint-disable-next-line no-console -- development fallback
    console.warn(`[telemetry] ${event.name} (${level})`, event.fields);
  }
}

function safeName(name: string): string {
  if (typeof name !== "string") return "unknown";
  const trimmed = name.trim();
  return trimmed ? trimmed.slice(0, 128) : "unknown";
}

function redactSensitive(fields: TelemetryFields): TelemetryFields {
  return Object.fromEntries(
    Object.entries(fields).map(([key, value]) => {
      const lowerKey = key.toLowerCase();
      const redact = !SAFE_KEY_EXCEPTIONS.has(lowerKey)
        && SENSITIVE_KEY_FRAGMENTS.some((fragment) => lowerKey.includes(fragment));
      return [key, redact ? "[redacted]" : value];
    }),
  );
}

function sendBeacon(endpoint: string, payload: Omit<TelemetryEvent, "timestamp">): void {
  try {
    const beacon = typeof navigator !== "undefined" ? navigator.sendBeacon?.bind(navigator) : undefined;
    beacon?.(endpoint, new Blob([JSON.stringify(payload)], { type: "application/json" }));
  } catch {
    // Telemetry remains best-effort.
  }
}

export function buildTelemetryEndpoint(apiBaseUrl: string): string {
  return `${(apiBaseUrl || "").replace(/\/+$/, "")}${TELEMETRY_EVENTS_PATH}`;
}

/** Build the anonymous, bounded backend collector; null means no backend URL. */
export function createBackendSink(apiBaseUrl: string): TelemetrySink | null {
  const endpoint = buildTelemetryEndpoint(apiBaseUrl);
  if (endpoint === TELEMETRY_EVENTS_PATH) return null;
  const inFlight = new Set<string>();

  return (event): void => {
    if (inFlight.has(event.name)) return;
    inFlight.add(event.name);
    const payload = { name: event.name, fields: event.fields, level: event.level };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), BACKEND_SINK_TIMEOUT_MS);
    const finish = () => {
      clearTimeout(timer);
      inFlight.delete(event.name);
    };
    try {
      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "omit",
        signal: controller.signal,
        keepalive: true,
      })
        .catch(() => sendBeacon(endpoint, payload))
        .finally(finish);
    } catch {
      finish();
      sendBeacon(endpoint, payload);
    }
  };
}

/** Test-only state reset. */
export function _resetTelemetry(): void {
  sink = null;
  consoleWarnedFor.clear();
}
