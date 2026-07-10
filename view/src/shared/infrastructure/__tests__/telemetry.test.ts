import { afterEach, beforeEach, describe, it } from "node:test";
import assert from "node:assert";
import {
  _getTelemetrySink,
  _resetTelemetry,
  buildTelemetryEndpoint,
  clearTelemetryDedup,
  createBackendSink,
  emitTelemetry,
  setTelemetrySink,
  type TelemetryEvent,
} from "../telemetry.ts";

const event = (name = "auth_bootstrap_transient"): TelemetryEvent => ({
  name, fields: { code: "timeout" }, level: "warn", timestamp: 1,
});

function captureWarnings(run: () => void): unknown[][] {
  const original = console.warn;
  const warnings: unknown[][] = [];
  console.warn = (...args: unknown[]) => warnings.push(args);
  try { run(); } finally { console.warn = original; }
  return warnings;
}

async function captureAsyncWarnings(run: () => void): Promise<unknown[][]> {
  const original = console.warn;
  const warnings: unknown[][] = [];
  console.warn = (...args: unknown[]) => warnings.push(args);
  try {
    run();
    await new Promise<void>((resolve) => setImmediate(resolve));
  } finally {
    console.warn = original;
  }
  return warnings;
}

beforeEach(_resetTelemetry);
afterEach(_resetTelemetry);

void describe("telemetry adapter", () => {
  void it("delivers stable events to the last registered sink", () => {
    const first: TelemetryEvent[] = [];
    const received: TelemetryEvent[] = [];
    setTelemetrySink((value) => first.push(value));
    setTelemetrySink((value) => received.push(value));
    emitTelemetry(" auth_bootstrap_transient ", { code: "timeout" }, "warn");
    assert.strictEqual(first.length, 0);
    assert.deepStrictEqual(received[0].fields, { code: "timeout" });
    assert.strictEqual(received[0].name, "auth_bootstrap_transient");
    assert.strictEqual(received[0].level, "warn");
    assert.ok(received[0].timestamp > 0);
  });

  void it("falls back once without a sink or when a sink fails", () => {
    for (const throws of [false, true]) {
      _resetTelemetry();
      if (throws) setTelemetrySink(() => { throw new Error("sink failed"); });
      const warnings = captureWarnings(() => {
        emitTelemetry("flapping", { n: 1 });
        emitTelemetry("flapping", { n: 2 });
      });
      assert.strictEqual(warnings.length, 1);
    }
  });

  void it("does not warn for a successful sink and null unregisters it", () => {
    let calls = 0;
    setTelemetrySink(() => { calls++; });
    assert.strictEqual(captureWarnings(() => emitTelemetry("healthy")).length, 0);
    setTelemetrySink(null);
    assert.strictEqual(_getTelemetrySink(), null);
    assert.strictEqual(captureWarnings(() => emitTelemetry("fallback")).length, 1);
    assert.strictEqual(calls, 1);
  });

  void it("resets one or all console dedup entries", () => {
    const warnings = captureWarnings(() => {
      emitTelemetry("one");
      clearTelemetryDedup("one");
      emitTelemetry("one");
      emitTelemetry("two");
      clearTelemetryDedup();
      emitTelemetry("one");
      emitTelemetry("two");
    });
    assert.strictEqual(warnings.length, 5);
  });

  void it("redacts every sensitive-key family but preserves approved operational fields", () => {
    const received: TelemetryEvent[] = [];
    setTelemetrySink((value) => received.push(value));
    const fields = {
      token: "x", cookie: "x", password: "x", secret: "x", api_key: "x", apiKey: "x",
      authorization: "x", credentials: "x", sessionId: "x", refresh_token: "x", requestHeader: "x",
      requestBody: "x", requestUrl: "x", userEmail: "x", token_prefix: "safe", count: 2, ok: true,
    };
    emitTelemetry("redaction", fields);
    for (const key of Object.keys(fields).filter((key) => !["token_prefix", "count", "ok"].includes(key))) {
      assert.strictEqual(received[0].fields[key], "[redacted]");
    }
    assert.deepStrictEqual(
      { token_prefix: received[0].fields.token_prefix, count: received[0].fields.count, ok: received[0].fields.ok },
      { token_prefix: "safe", count: 2, ok: true },
    );
  });

  void it("normalizes invalid names and defaults the level", () => {
    const received: TelemetryEvent[] = [];
    setTelemetrySink((value) => received.push(value));
    emitTelemetry("   ", { nil: null });
    emitTelemetry(123 as unknown as string);
    assert.deepStrictEqual(received.map(({ name, level, fields }) => ({ name, level, fields })), [
      { name: "unknown", level: "info", fields: { nil: null } },
      { name: "unknown", level: "info", fields: {} },
    ]);
  });
});

void describe("backend telemetry sink", () => {
  const originalFetch = globalThis.fetch;
  const originalNavigator = globalThis.navigator;
  afterEach(() => {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "navigator", { value: originalNavigator, configurable: true, writable: true });
  });

  void it("builds endpoints and skips an unconfigured backend", () => {
    assert.strictEqual(buildTelemetryEndpoint("https://api.test/"), "https://api.test/telemetry/events");
    assert.strictEqual(createBackendSink(""), null);
  });

  void it("posts anonymously with the expected payload", async () => {
    let url = "";
    let init: RequestInit | undefined;
    globalThis.fetch = ((value, options) => {
      url = String(value); init = options; return Promise.resolve(new Response("", { status: 202 }));
    }) as typeof fetch;
    createBackendSink("https://api.test")!(event());
    await Promise.resolve();
    assert.strictEqual(url, "https://api.test/telemetry/events");
    assert.deepStrictEqual(JSON.parse(String(init!.body)), { name: event().name, fields: event().fields, level: event().level });
    assert.strictEqual(init!.credentials, "omit");
    assert.ok(init!.signal);
    assert.ok(init!.keepalive);
  });

  void it("falls back to a beacon for rejected or synchronous fetch failures", async () => {
    for (const fetchImpl of [
      () => Promise.reject(new Error("offline")),
      () => { throw new TypeError("invalid URL"); },
    ]) {
      _resetTelemetry();
      let beacons = 0;
      Object.defineProperty(globalThis, "navigator", { value: { sendBeacon: () => { beacons++; return true; } }, configurable: true });
      globalThis.fetch = fetchImpl as typeof fetch;
      assert.doesNotThrow(() => createBackendSink("https://api.test")!(event()));
      await new Promise<void>((resolve) => setImmediate(resolve));
      assert.strictEqual(beacons, 1);
    }
  });

  void it("falls back to a beacon for non-success HTTP responses", async () => {
    for (const status of [400, 500]) {
      let beacons = 0;
      Object.defineProperty(globalThis, "navigator", { value: { sendBeacon: () => { beacons++; return true; } }, configurable: true });
      globalThis.fetch = (() => Promise.resolve(new Response("", { status }))) as typeof fetch;
      createBackendSink("https://api.test")!(event(`http_${status}`));
      await new Promise(setImmediate);
      assert.strictEqual(beacons, 1);
    }
  });

  void it("uses the console fallback when the beacon is unavailable or fails", async () => {
    for (const sendBeacon of [undefined, () => false]) {
      Object.defineProperty(globalThis, "navigator", { value: { sendBeacon }, configurable: true });
      globalThis.fetch = (() => Promise.reject(new Error("offline"))) as typeof fetch;
      const warnings = await captureAsyncWarnings(() => createBackendSink("https://api.test")!(event(`beacon_${String(sendBeacon)}`)));
      assert.strictEqual(warnings.length, 1);
    }
  });

  void it("bounds total in-flight deliveries and recovers after a permit releases", async () => {
    const originalSetTimeout = globalThis.setTimeout;
    const originalClearTimeout = globalThis.clearTimeout;
    const pending: Array<(response: Response) => void> = [];
    let calls = 0;
    globalThis.setTimeout = (() => 0) as unknown as typeof setTimeout;
    globalThis.clearTimeout = (() => {}) as typeof clearTimeout;
    globalThis.fetch = (() => {
      calls++;
      return new Promise<Response>((resolve) => pending.push(resolve));
    }) as typeof fetch;
    try {
      const sinks = [createBackendSink("https://api.test")!, createBackendSink("https://api.test")!];
      const warnings = captureWarnings(() => {
        for (let index = 0; index < 10; index++) sinks[index % 2](event(`unique_${index}`));
        sinks[0](event("saturated"));
      });
      assert.strictEqual(calls, 10);
      assert.strictEqual(warnings.length, 1);
      pending.shift()!(new Response());
      await new Promise<void>((resolve) => setImmediate(resolve));
      sinks[0](event("recovered"));
      assert.strictEqual(calls, 11);
    } finally {
      globalThis.setTimeout = originalSetTimeout;
      globalThis.clearTimeout = originalClearTimeout;
    }
  });

  void it("does not create a request or timeout while saturated", () => {
    const originalSetTimeout = globalThis.setTimeout;
    const originalClearTimeout = globalThis.clearTimeout;
    let calls = 0;
    let timers = 0;
    globalThis.fetch = (() => { calls++; return new Promise<Response>(() => {}); }) as typeof fetch;
    globalThis.setTimeout = (() => {
      timers++;
      return 0;
    }) as unknown as typeof setTimeout;
    globalThis.clearTimeout = (() => {}) as typeof clearTimeout;
    try {
      const sink = createBackendSink("https://api.test")!;
      for (let index = 0; index < 10; index++) sink(event(`pending_${index}`));
      sink(event("no_leak"));
      assert.strictEqual(calls, 10);
      assert.strictEqual(timers, 10);
    } finally {
      globalThis.setTimeout = originalSetTimeout;
      globalThis.clearTimeout = originalClearTimeout;
    }
  });

  void it("dedupes in-flight events and integrates with emitTelemetry", async () => {
    let calls = 0;
    let release: (response: Response) => void;
    globalThis.fetch = (() => { calls++; return new Promise<Response>((resolve) => { release = resolve; }); }) as typeof fetch;
    const sink = createBackendSink("https://api.test")!;
    sink(event()); sink(event());
    assert.strictEqual(calls, 1);
    _resetTelemetry();
    globalThis.fetch = (() => { calls++; return Promise.resolve(new Response()); }) as typeof fetch;
    setTelemetrySink(createBackendSink("https://api.test"));
    emitTelemetry("integrated");
    await Promise.resolve();
    assert.strictEqual(calls, 2);
    release!(new Response());
    await new Promise<void>((resolve) => setImmediate(resolve));
  });
});
