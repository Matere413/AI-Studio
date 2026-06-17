import { describe, it, expect, vi, beforeEach } from "vitest";
import { submitGenerate, getWsUrl } from "./api";

describe("submitGenerate (Spec: API Integration — Scenario: Submit)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts prompt and params to /api/generate and returns job_id + status", async () => {
    const mockResponse = { job_id: "abc-123", status: "pending" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await submitGenerate("A fiery sunset", {
      workflow_name: "txt2img",
    });

    expect(result).toEqual({ job_id: "abc-123", status: "pending" });
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "A fiery sunset",
        workflow: "txt2img",
        workflow_name: "txt2img",
        format: "square",
      }),
    });
  });

  it("includes checkpoint_url and lora_url when provided", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "xyz-789", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await submitGenerate("test prompt", {
      workflow_name: "controlnet",
      checkpoint_url: "http://example.com/model.safetensors",
      lora_url: "http://example.com/lora.safetensors",
    });

    const fetchCall = (
      globalThis.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody.checkpoint_url).toBe(
      "http://example.com/model.safetensors"
    );
    expect(callBody.lora_url).toBe("http://example.com/lora.safetensors");
  });

  it("throws on non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 })
    );

    await expect(
      submitGenerate("test", { workflow_name: "txt2img" })
    ).rejects.toThrow("Generation request failed: 400");
  });

  it("throws on network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(
      new TypeError("Failed to fetch")
    );

    await expect(
      submitGenerate("test", { workflow_name: "txt2img" })
    ).rejects.toThrow("Failed to fetch");
  });
});

describe("getWsUrl (Spec: API Integration — Scenario: WS URL)", () => {
  it("returns the correct WebSocket URL for a job_id", () => {
    expect(getWsUrl("abc-123")).toBe("/api/ws/generate/abc-123");
  });

  it("returns the correct URL for a different job_id", () => {
    expect(getWsUrl("job-xyz-456")).toBe("/api/ws/generate/job-xyz-456");
  });
});
