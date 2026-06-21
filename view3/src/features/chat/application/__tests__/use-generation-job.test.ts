// ─── Unit Tests: generation job reducer ───────────────────────
// Tests the pure state machine used by useGenerationJob.
// The reducer handles WebSocket lifecycle state transitions,
// event accumulation, and retry exhaustion logic.
//
// This file covers Tasks 2.2 + 2.6 (reducer logic + hook behavior).

import { describe, it, mock, afterEach, beforeEach } from "node:test";
import assert from "node:assert";
import {
  wsReducer,
  initialState,
  RETRY_DELAYS_MS,
} from "../use-generation-job.ts";
import type { JobEvent } from "../../../studio/domain/dto.ts";

// ─── Helpers ──────────────────────────────────────────────────

function messageEvent(event: JobEvent) {
  return { type: "MESSAGE" as const, event };
}

// ─── Tests ────────────────────────────────────────────────────

void describe("wsReducer", () => {
  // ── Initial State ──────────────────────────────────────────

  void it("starts with idle/connecting state", () => {
    assert.strictEqual(initialState.state, "connecting");
    assert.strictEqual(initialState.events.length, 0);
    assert.strictEqual(initialState.progress, 0);
    assert.strictEqual(initialState.retryCount, 0);
  });

  // ── CONNECTING ────────────────────────────────────────────

  void it("CONNECTING transitions to connecting state", () => {
    const result = wsReducer(initialState, { type: "CONNECTING" });
    assert.strictEqual(result.state, "connecting");
    assert.strictEqual(result.retryCount, initialState.retryCount);
  });

  // ── CONNECTED ─────────────────────────────────────────────

  void it("CONNECTED transitions from connecting → streaming", () => {
    const state = wsReducer(initialState, { type: "CONNECTING" });
    const result = wsReducer(state, { type: "CONNECTED" });
    assert.strictEqual(result.state, "streaming");
  });

  void it("CONNECTED is ignored when not in connecting state", () => {
    const result = wsReducer(
      { ...initialState, state: "streaming" },
      { type: "CONNECTED" },
    );
    assert.strictEqual(result.state, "streaming");
  });

  // ── MESSAGE: progress events ──────────────────────────────

  void it("MESSAGE with progress updates state and progress", () => {
    const state = wsReducer(
      { ...initialState, state: "streaming" },
      messageEvent({
        event: "progress",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        progress: 42,
      }),
    );
    assert.strictEqual(state.state, "streaming");
    assert.strictEqual(state.progress, 42);
    assert.strictEqual(state.events.length, 1);
    assert.strictEqual(state.events[0].event, "progress");
  });

  void it("MESSAGE accumulates multiple events", () => {
    const afterFirst = wsReducer(
      { ...initialState, state: "streaming" },
      messageEvent({
        event: "booting_server",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
      }),
    );
    const afterSecond = wsReducer(
      afterFirst,
      messageEvent({
        event: "progress",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:01Z",
        progress: 50,
      }),
    );
    assert.strictEqual(afterSecond.events.length, 2);
    assert.strictEqual(afterSecond.progress, 50);
  });

  void it("MESSAGE is ignored when not streaming", () => {
    const result = wsReducer(
      { ...initialState, state: "completed" },
      messageEvent({
        event: "progress",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        progress: 50,
      }),
    );
    assert.strictEqual(result.events.length, 0);
    assert.strictEqual(result.state, "completed");
  });

  // ── MESSAGE: completed event ──────────────────────────────

  void it("MESSAGE completed transitions to completed state", () => {
    const state = wsReducer(
      { ...initialState, state: "streaming" },
      messageEvent({
        event: "completed",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        result: { image_path: "/media/result.png" },
      }),
    );
    assert.strictEqual(state.state, "completed");
    assert.strictEqual(state.events.length, 1);
    const evt = state.events[0] as JobEvent & { result: { image_path: string } };
    assert.strictEqual(evt.result.image_path, "/media/result.png");
  });

  // ── MESSAGE: error event ──────────────────────────────────

  void it("MESSAGE error transitions to error state", () => {
    const state = wsReducer(
      { ...initialState, state: "streaming" },
      messageEvent({
        event: "error",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        error: { code: "generation_failed", detail: "GPU OOM" },
      }),
    );
    assert.strictEqual(state.state, "error");
    assert.strictEqual(state.events.length, 1);
    const evt = state.events[0] as JobEvent & { error: { code: string } };
    assert.strictEqual(evt.error.code, "generation_failed");
  });

  // ── WS_ERROR — Non-terminal disconnect ────────────────────

  void it("WS_ERROR increments retryCount and transitions to error state (< 3 retries)", () => {
    const result = wsReducer(
      { ...initialState, state: "streaming", retryCount: 0 },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(result.state, "error");
    assert.strictEqual(result.retryCount, 1);
  });

  void it("WS_ERROR on 2nd retry increments to 3 and goes to exhausted", () => {
    const result = wsReducer(
      { ...initialState, state: "streaming", retryCount: 2 },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(result.state, "exhausted");
    assert.strictEqual(result.retryCount, 3);
  });

  void it("WS_ERROR on 3rd retry stays exhausted", () => {
    const result = wsReducer(
      { ...initialState, state: "streaming", retryCount: 3 },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(result.state, "exhausted");
    assert.strictEqual(result.retryCount, 3);
  });

  // ── RETRY_RESET ───────────────────────────────────────────

  void it("RETRY_RESET resets retryCount to 0 and transitions to connecting", () => {
    const result = wsReducer(
      { ...initialState, state: "exhausted", retryCount: 3 },
      { type: "RETRY_RESET" },
    );
    assert.strictEqual(result.state, "connecting");
    assert.strictEqual(result.retryCount, 0);
    // Events and progress preserved
    assert.deepStrictEqual(result.events, []);
  });

  // ── Full lifecycle: connect → progress → complete ─────────

  void it("full lifecycle: connecting → streaming → completed", () => {
    const s1 = wsReducer(initialState, { type: "CONNECTING" });
    assert.strictEqual(s1.state, "connecting");

    const s2 = wsReducer(s1, { type: "CONNECTED" });
    assert.strictEqual(s2.state, "streaming");

    const s3 = wsReducer(s2, messageEvent({
      event: "booting_server",
      job_id: "j1",
      timestamp: "2026-01-01T00:00:00Z",
    }));
    assert.strictEqual(s3.state, "streaming");
    assert.strictEqual(s3.events.length, 1);

    const s4 = wsReducer(s3, messageEvent({
      event: "generating",
      job_id: "j1",
      timestamp: "2026-01-01T00:00:01Z",
    }));
    assert.strictEqual(s4.state, "streaming");
    assert.strictEqual(s4.events.length, 2);

    const s5 = wsReducer(s4, messageEvent({
      event: "progress",
      job_id: "j1",
      timestamp: "2026-01-01T00:00:01Z",
      progress: 75,
    }));
    assert.strictEqual(s5.state, "streaming");
    assert.strictEqual(s5.progress, 75);

    const s6 = wsReducer(s5, messageEvent({
      event: "completed",
      job_id: "j1",
      timestamp: "2026-01-01T00:00:02Z",
      result: { image_path: "/media/out.png" },
    }));
    assert.strictEqual(s6.state, "completed");
    assert.strictEqual(s6.events.length, 4);
  });

  // ── Full lifecycle: retry exhaustion → retry() reset ──────

  void it("exhaustion cycle: error → error → exhausted → retry → connecting", () => {
    // 1st error
    const s1 = wsReducer(
      { ...initialState, state: "streaming" },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(s1.state, "error");
    assert.strictEqual(s1.retryCount, 1);

    // 2nd error
    const s2 = wsReducer(
      { ...s1, state: "streaming" },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(s2.state, "error");
    assert.strictEqual(s2.retryCount, 2);

    // 3rd error → exhausted
    const s3 = wsReducer(
      { ...s2, state: "streaming" },
      { type: "WS_ERROR" },
    );
    assert.strictEqual(s3.state, "exhausted");
    assert.strictEqual(s3.retryCount, 3);

    // retry() resets
    const s4 = wsReducer(s3, { type: "RETRY_RESET" });
    assert.strictEqual(s4.state, "connecting");
    assert.strictEqual(s4.retryCount, 0);
  });

  // ── Reconnect success: WS_ERROR → CONNECTING → stream resumes ──

  void it("reconnect success: WS_ERROR → CONNECTING → CONNECTED → stream resumes with new events", () => {
    // Start streaming with events
    const s1 = wsReducer(
      { ...initialState, state: "streaming", events: [], progress: 50 },
      messageEvent({
        event: "progress", job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z", progress: 50,
      }),
    );
    assert.strictEqual(s1.events.length, 1);
    assert.strictEqual(s1.progress, 50);

    // Disconnect
    const s2 = wsReducer(s1, { type: "WS_ERROR" });
    assert.strictEqual(s2.state, "error");
    assert.strictEqual(s2.retryCount, 1);

    // Reconnect
    const s3 = wsReducer(s2, { type: "CONNECTING" });
    assert.strictEqual(s3.state, "connecting");

    // Connection established
    const s4 = wsReducer(s3, { type: "CONNECTED" });
    assert.strictEqual(s4.state, "streaming");
    // Events from previous session are preserved
    assert.strictEqual(s4.events.length, 1);

    // New events arrive — stream resumed!
    const s5 = wsReducer(s4, messageEvent({
      event: "progress", job_id: "j1",
      timestamp: "2026-01-01T00:00:03Z", progress: 65,
    }));
    assert.strictEqual(s5.state, "streaming");
    assert.strictEqual(s5.events.length, 2);  // Previous event + new event
    assert.strictEqual(s5.progress, 65);       // Updated to new progress

    // Stream continues to completion
    const s6 = wsReducer(s5, messageEvent({
      event: "completed", job_id: "j1",
      timestamp: "2026-01-01T00:00:04Z",
      result: { image_path: "/media/reconnected.png" },
    }));
    assert.strictEqual(s6.state, "completed");
    assert.strictEqual(s6.events.length, 3);
    const lastEvent = s6.events[2] as JobEvent & { result: { image_path: string } };
    assert.strictEqual(lastEvent.result.image_path, "/media/reconnected.png");
  });

  // ── Backoff timing: verify constants ────────────────────

  void it("backoff delays are [1_000, 2_000, 4_000] ms", () => {
    assert.deepStrictEqual(RETRY_DELAYS_MS, [1_000, 2_000, 4_000]);
    assert.strictEqual(RETRY_DELAYS_MS.length, 3);
  });

  // ── Edge cases ────────────────────────────────────────────

  void it("unknown action type returns state unchanged", () => {
    const result = wsReducer(initialState, { type: "UNKNOWN" } as never);
    assert.strictEqual(result, initialState);
  });
});

// ═══════════════════════════════════════════════════════════════
// Hook-level tests: useGenerationJob reconnect behavior
// ═══════════════════════════════════════════════════════════════
// Tests the actual React hook using react-test-renderer with a
// mocked WebSocket and Node's mock.timers for fake time advancement.
//
// Proves: WS close → backoff timer → new WebSocket instance created.

import React from "react";
import {
  create as createTestRenderer,
  act,
} from "react-test-renderer";
import {
  useGenerationJob as useGenJob,
} from "../use-generation-job.ts";
import type { UseGenerationJobResult } from "../use-generation-job.ts";

// ─── Mock WebSocket ────────────────────────────────────────────

let wsCallCount: number;
let wsInstances: any[];

class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  url: string;
  readyState: number;
  onopen: null | ((event?: any) => void);
  onclose: null | ((event?: any) => void);
  onerror: null | ((event?: any) => void);
  onmessage: null | ((event?: any) => void);

  constructor(url: string) {
    wsCallCount++;
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onopen = null;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    wsInstances.push(this);
  }

  close(): void {
    // Tests trigger onclose manually — no-op by design
  }
}

function getLatestWs(): any {
  return wsInstances[wsInstances.length - 1];
}

// ─── Test Harness Component ────────────────────────────────────

let latestHookResult: UseGenerationJobResult | null;

function Harness({ jobId }: { jobId: string | null }) {
  latestHookResult = useGenJob(
    jobId,
    MockWebSocket as unknown as typeof WebSocket,
  );
  return null;
}

// ─── Tests ─────────────────────────────────────────────────────

void describe("useGenerationJob hook — reconnect", () => {
  let root: ReturnType<typeof createTestRenderer>;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000";
    wsCallCount = 0;
    wsInstances = [];
    latestHookResult = null;
  });

  afterEach(() => {
    if (root) {
      act(() => {
        root.unmount();
      });
    }
    mock.timers.reset();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    wsCallCount = 0;
    wsInstances = [];
    latestHookResult = null;
  });

  void it(
    "creates a new WebSocket instance after close + backoff timer expires",
    async () => {
      mock.timers.enable({ apis: ["setTimeout"] });

      // ── Render the hook with a jobId ────────────────────
      await act(async () => {
        root = createTestRenderer(
          React.createElement(Harness, { jobId: "j1" }),
        );
      });

      // 1. Initial connection → "connecting", 1 WS created
      assert.strictEqual(wsCallCount, 1);
      assert.strictEqual(latestHookResult?.state, "connecting");

      // 2. Connection established → "streaming"
      await act(async () => {
        getLatestWs().onopen!();
      });
      assert.strictEqual(latestHookResult?.state, "streaming");

      // 3. Unexpected close → "error" + retryCount bumps to 1
      //    The auto-retry effect fires setTimeout with backoff
      await act(async () => {
        getLatestWs().onclose!();
      });
      assert.strictEqual(latestHookResult?.state, "error");
      assert.strictEqual(latestHookResult?.retryCount, 1);

      // 4. Advance the backoff timer — fires the auto-retry callback
      //    which dispatches CONNECTING and increments connectKey
      await act(async () => {
        mock.timers.tick(RETRY_DELAYS_MS[0]);
      });

      // 5. A new WebSocket must have been created (reconnect!)
      assert.strictEqual(wsCallCount, 2);
      assert.strictEqual(latestHookResult?.state, "connecting");
    },
  );
});
