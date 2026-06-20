// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_WS_MAX_RETRIES,
  DEFAULT_WS_RETRY_DELAY,
  connectWebSocket,
  getImageUrl,
  getWsUrl,
  submitGenerate,
} from "./client";

describe("generation API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("posts workflow-specific payloads without unsupported fields", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "job-1", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await submitGenerate("A studio portrait", {
      workflow_name: "flux2_txt2img",
    });

    const requestInit = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const body = JSON.parse(requestInit.body as string) as Record<string, unknown>;

    expect(body).toMatchObject({
      prompt: "A studio portrait",
      workflow: "flux2_txt2img",
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });
    expect(body).not.toHaveProperty("aspect_ratio");
  });

  it("posts editing and identity payloads with only the supported fields", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ job_id: "job-2", status: "pending" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ job_id: "job-3", status: "pending" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    await submitGenerate("Edit this image", {
      workflow_name: "flux2_editing",
      use_turbo: false,
      image_base64: "data:image/png;base64,ZWQ=",
    });

    let requestInit = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    let body = JSON.parse(requestInit.body as string) as Record<string, unknown>;

    expect(body).toMatchObject({
      workflow_name: "flux2_editing",
      image_base64: "data:image/png;base64,ZWQ=",
      use_turbo: false,
    });
    expect(body).not.toHaveProperty("aspect_ratio");

    await submitGenerate("Preserve identity", {
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,aWRlbnRpdHk=",
      width: 768,
      height: 1024,
      seed: 17,
    });

    requestInit = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[1][1] as RequestInit;
    body = JSON.parse(requestInit.body as string) as Record<string, unknown>;

    expect(body).toMatchObject({
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,aWRlbnRpdHk=",
      width: 768,
      height: 1024,
      seed: 17,
    });
    expect(body).not.toHaveProperty("use_turbo");
    expect(body).not.toHaveProperty("aspect_ratio");
  });

  it("returns the expected URLs", () => {
    expect(getWsUrl("abc-123")).toBe("/api/ws/generate/abc-123");
    expect(getImageUrl("abc-123")).toBe("/api/images/abc-123");
  });

  it("retries the websocket with exponential backoff and stops after the limit", async () => {
    const instances: Array<{
      onopen: (() => void) | null;
      onmessage: ((event: { data: string }) => void) | null;
      onclose: ((event: { code: number; reason: string }) => void) | null;
      close: (code?: number, reason?: string) => void;
    }> = [];

    const MockWebSocket = class {
      url: string;
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onclose: ((event: { code: number; reason: string }) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }

      close(code = 1000, reason = "") {
        this.onclose?.({ code, reason });
      }
    };

    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();

    let exhausted = false;
    const cleanup = connectWebSocket("/api/ws/generate/job-3", {
      onEvent: () => undefined,
      onExhausted: () => {
        exhausted = true;
      },
      maxRetries: 3,
      retryDelay: 100,
    });

    expect(instances).toHaveLength(1);
    instances[0].onclose?.({ code: 1006, reason: "abnormal" });

    await vi.advanceTimersByTimeAsync(100);
    expect(instances).toHaveLength(2);
    instances[1].onclose?.({ code: 1006, reason: "abnormal" });

    await vi.advanceTimersByTimeAsync(200);
    expect(instances).toHaveLength(3);
    instances[2].onclose?.({ code: 1006, reason: "abnormal" });

    await vi.advanceTimersByTimeAsync(400);
    expect(instances).toHaveLength(4);
    instances[3].onclose?.({ code: 1006, reason: "abnormal" });

    expect(exhausted).toBe(true);

    cleanup();
  });

  it("exhausts retries after repeated open and abnormal close cycles", async () => {
    const instances: Array<{
      onopen: (() => void) | null;
      onmessage: ((event: { data: string }) => void) | null;
      onclose: ((event: { code: number; reason: string }) => void) | null;
      close: (code?: number, reason?: string) => void;
    }> = [];

    const MockWebSocket = class {
      url: string;
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onclose: ((event: { code: number; reason: string }) => void) | null = null;

      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }

      close(code = 1000, reason = "") {
        this.onclose?.({ code, reason });
      }
    };

    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();

    let exhausted = false;
    connectWebSocket("/api/ws/generate/job-4", {
      onEvent: () => undefined,
      onExhausted: () => {
        exhausted = true;
      },
      maxRetries: DEFAULT_WS_MAX_RETRIES,
      retryDelay: DEFAULT_WS_RETRY_DELAY,
    });

    expect(instances).toHaveLength(1);

    for (let attempt = 0; attempt <= DEFAULT_WS_MAX_RETRIES; attempt += 1) {
      instances[attempt].onopen?.();
      instances[attempt].onclose?.({ code: 1006, reason: "abnormal" });
      await vi.advanceTimersByTimeAsync(DEFAULT_WS_RETRY_DELAY * 2 ** attempt);
    }

    expect(exhausted).toBe(true);
    expect(instances).toHaveLength(DEFAULT_WS_MAX_RETRIES + 1);
  });
});
