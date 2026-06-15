import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { connectWebSocket } from "./client";

describe("connectWebSocket (Spec: WebSocket — Scenarios: Successful stream, Reconnect, Retries exhausted)", () => {
  let instances: Array<{
    url: string;
    onopen: (() => void) | null;
    onmessage: ((ev: { data: string }) => void) | null;
    onerror: ((ev: { error?: Error }) => void) | null;
    onclose: ((ev: { code: number; reason: string }) => void) | null;
    close: (code?: number, reason?: string) => void;
  }> = [];

  function createMockWS() {
    instances = [];
    const MockWS = class {
      url: string;
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onerror: ((ev: { error?: Error }) => void) | null = null;
      onclose: ((ev: { code: number; reason: string }) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }

      close(code = 1000, reason = "") {
        this.onclose?.({ code, reason });
      }
    };
    vi.stubGlobal("WebSocket", MockWS);
    return MockWS;
  }

  beforeEach(() => {
    instances = [];
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("connects to the correct URL and calls onEvent for each message", () => {
    createMockWS();
    const events: unknown[] = [];
    const onEvent = (event: unknown) => events.push(event);

    connectWebSocket("/api/ws/generate/job-1", {
      onEvent,
      maxRetries: 0,
    });

    expect(instances).toHaveLength(1);
    expect(instances[0].url).toContain("/api/ws/generate/job-1");

    // Simulate open
    instances[0].onopen?.();

    // Simulate messages
    instances[0].onmessage?.({
      data: JSON.stringify({
        event: "running",
        job_id: "job-1",
        timestamp: "2024-01-01T00:00:00Z",
      }),
    });
    instances[0].onmessage?.({
      data: JSON.stringify({
        event: "completed",
        job_id: "job-1",
        timestamp: "2024-01-01T00:01:00Z",
        result: { image_path: "/images/out.png" },
      }),
    });

    expect(events).toHaveLength(2);
    expect((events[0] as Record<string, unknown>).event).toBe("running");
    expect((events[1] as Record<string, unknown>).event).toBe("completed");
  });

  it("retries on abnormal close with exponential backoff (Spec: Reconnect succeeds)", async () => {
    createMockWS();
    vi.useFakeTimers();

    const events: unknown[] = [];
    const onEvent = (event: unknown) => events.push(event);

    connectWebSocket("/api/ws/generate/job-2", {
      onEvent,
      maxRetries: 3,
      retryDelay: 100,
    });

    // First connection
    expect(instances).toHaveLength(1);

    // Simulate abnormal close (triggers retry)
    instances[0].onclose?.({ code: 1006, reason: "abnormal" });

    // After retry delay (100ms × 2^0 = 100ms)
    await vi.advanceTimersByTimeAsync(150);
    expect(instances).toHaveLength(2);

    // Second connection succeeds — simulate open
    instances[1].onopen?.();

    // Send a message through the second connection
    instances[1].onmessage?.({
      data: JSON.stringify({
        event: "running",
        job_id: "job-2",
        timestamp: "2024-01-01T00:00:00Z",
      }),
    });

    expect(events).toHaveLength(1);
  });

  it("calls onExhausted after max retries exhausted (Spec: Retries exhausted)", async () => {
    createMockWS();
    vi.useFakeTimers();
    let exhaustedCalled = false;

    const onEvent = () => {};
    const onExhausted = () => {
      exhaustedCalled = true;
    };

    connectWebSocket("/api/ws/generate/job-3", {
      onEvent,
      onExhausted,
      maxRetries: 3,
      retryDelay: 50,
    });

    // First connection closes abnormally
    instances[0].onclose?.({ code: 1006, reason: "abnormal" });

    // Retry 1 (50ms delay)
    await vi.advanceTimersByTimeAsync(100);
    expect(instances).toHaveLength(2);
    instances[1].onclose?.({ code: 1006, reason: "abnormal" });

    // Retry 2 (100ms delay)
    await vi.advanceTimersByTimeAsync(200);
    expect(instances).toHaveLength(3);
    instances[2].onclose?.({ code: 1006, reason: "abnormal" });

    // Retry 3 (200ms delay)
    await vi.advanceTimersByTimeAsync(300);
    expect(instances).toHaveLength(4);
    instances[3].onclose?.({ code: 1006, reason: "abnormal" });

    // After all retries exhausted, onExhausted should be called
    expect(exhaustedCalled).toBe(true);
  });

  it("does not retry on normal close (code 1000)", async () => {
    createMockWS();
    vi.useFakeTimers();

    connectWebSocket("/api/ws/generate/job-4", {
      onEvent: () => {},
      maxRetries: 3,
      retryDelay: 50,
    });

    expect(instances).toHaveLength(1);

    // Close normally
    instances[0].onclose?.({ code: 1000, reason: "normal" });

    // Advance time — no retry should happen
    await vi.advanceTimersByTimeAsync(500);
    expect(instances).toHaveLength(1);
  });

  it("cleanup function closes the WebSocket and prevents retries", async () => {
    createMockWS();
    vi.useFakeTimers();

    const cleanup = connectWebSocket("/api/ws/generate/job-5", {
      onEvent: () => {},
      maxRetries: 3,
      retryDelay: 50,
    });

    expect(instances).toHaveLength(1);

    // Call cleanup — should close the WebSocket
    cleanup();

    // Advance time — no retry should happen
    await vi.advanceTimersByTimeAsync(500);
    expect(instances).toHaveLength(1);
  });
});
