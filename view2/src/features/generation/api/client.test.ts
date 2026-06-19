import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  connectWebSocket,
  getImageUrl,
  getWsUrl,
  submitGenerate,
} from "./client";
import { JOB_EVENT_NAMES, WORKFLOW_NAMES } from "./types";

describe("generation API contracts", () => {
  it("keeps frontend workflow and event names aligned to the backend enum", () => {
    expect(WORKFLOW_NAMES).toEqual([
      "flux2_txt2img",
      "flux2_editing",
      "identidad_gguf",
    ]);
    expect(JOB_EVENT_NAMES).toEqual([
      "booting_server",
      "downloading_weights",
      "generating",
      "progress",
      "completed",
      "error",
    ]);
  });
});

describe("submitGenerate", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts Flux text-to-image requests with turbo defaulted to true", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "job-flux", status: "pending" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(
      submitGenerate("A dark cinematic product render", {
        workflow_name: "flux2_txt2img",
      })
    ).resolves.toEqual({ job_id: "job-flux", status: "pending" });

    const [, requestInit] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(requestInit?.body as string)).toMatchObject({
      prompt: "A dark cinematic product render",
      workflow: "flux2_txt2img",
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });
  });

  it("posts Flux editing requests with image_base64 and explicit turbo", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "job-edit", status: "pending" }), {
        status: 202,
      })
    );

    await submitGenerate("Edit this reference", {
      workflow_name: "flux2_editing",
      use_turbo: false,
      image_base64: "data:image/png;base64,ZmFrZQ==",
    });

    const [, requestInit] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(requestInit?.body as string)).toMatchObject({
      workflow: "flux2_editing",
      workflow_name: "flux2_editing",
      use_turbo: false,
      image_base64: "data:image/png;base64,ZmFrZQ==",
    });
  });

  it("posts identity requests without Flux-only fields", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "job-id", status: "pending" }), {
        status: 202,
      })
    );

    await submitGenerate("Preserve this identity", {
      workflow_name: "identidad_gguf",
      image_url: "data:image/jpeg;base64,aWQ=",
      width: 768,
      height: 1024,
      seed: -1,
    });

    const [, requestInit] = vi.mocked(globalThis.fetch).mock.calls[0];
    const body = JSON.parse(requestInit?.body as string);
    expect(body).toMatchObject({
      workflow: "identidad_gguf",
      workflow_name: "identidad_gguf",
      image_url: "data:image/jpeg;base64,aWQ=",
      width: 768,
      height: 1024,
      seed: -1,
    });
    expect(body).not.toHaveProperty("use_turbo");
    expect(body).not.toHaveProperty("image_base64");
  });

  it("throws a useful error when the backend rejects the request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 })
    );

    await expect(
      submitGenerate("Invalid", { workflow_name: "flux2_txt2img" })
    ).rejects.toThrow("Generation request failed: 400");
  });
});

describe("generation URLs", () => {
  it("builds relative WS and image URLs for Next rewrites", () => {
    expect(getWsUrl("job 1/2")).toBe("/api/ws/generate/job%201%2F2");
    expect(getImageUrl("job 1/2")).toBe("/api/images/job%201%2F2");
  });
});

describe("connectWebSocket", () => {
  const instances: Array<{
    url: string;
    onmessage: ((event: { data: string }) => void) | null;
    onclose: ((event: { code: number }) => void) | null;
    close: ReturnType<typeof vi.fn>;
  }> = [];

  beforeEach(() => {
    vi.useFakeTimers();
    instances.length = 0;
    class MockWebSocket {
      url: string;
      onmessage: ((event: { data: string }) => void) | null = null;
      onclose: ((event: { code: number }) => void) | null = null;
      close = vi.fn();

      constructor(url: string) {
        this.url = url;
        instances.push(this);
      }
    }
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  it("dispatches JSON messages and ignores malformed frames", () => {
    const onEvent = vi.fn();

    connectWebSocket("/api/ws/generate/job-1", { onEvent, maxRetries: 0 });
    instances[0].onmessage?.({ data: "not json" });
    instances[0].onmessage?.({
      data: JSON.stringify({
        event: "booting_server",
        job_id: "job-1",
        timestamp: "2026-06-18T00:00:00.000Z",
      }),
    });

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ event: "booting_server" })
    );
  });

  it("retries abnormal closes with exponential backoff then exhausts", async () => {
    const onExhausted = vi.fn();

    connectWebSocket("/api/ws/generate/job-2", {
      onEvent: vi.fn(),
      onExhausted,
      maxRetries: 3,
      retryDelay: 100,
    });

    instances[0].onclose?.({ code: 1006 });
    await vi.advanceTimersByTimeAsync(100);
    instances[1].onclose?.({ code: 1006 });
    await vi.advanceTimersByTimeAsync(200);
    instances[2].onclose?.({ code: 1006 });
    await vi.advanceTimersByTimeAsync(400);
    instances[3].onclose?.({ code: 1006 });

    expect(instances).toHaveLength(4);
    expect(onExhausted).toHaveBeenCalledTimes(1);
  });

  it("cleanup closes the current socket and prevents retries", async () => {
    const cleanup = connectWebSocket("/api/ws/generate/job-3", {
      onEvent: vi.fn(),
      maxRetries: 3,
      retryDelay: 100,
    });

    cleanup();
    instances[0].onclose?.({ code: 1006 });
    await vi.advanceTimersByTimeAsync(500);

    expect(instances[0].close).toHaveBeenCalledWith(1000, "User cancelled");
    expect(instances).toHaveLength(1);
  });
});
