import { describe, it, expect, vi, beforeEach } from "vitest";
import { submitGenerate, getWsUrl } from "./client";
import type { GenerationParameters } from "./types";

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

  it("includes realistic persona controls in the request payload", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "persona-123", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const params = {
      workflow_name: "realistic_persona",
      age: 34,
      gender: "woman",
      ethnicity: "latina",
      wardrobe: "linen blazer",
      expression: "calm smile",
      background: "sunlit studio",
      output_type: "editorial",
    } satisfies GenerationParameters;

    await submitGenerate("Natural portrait with soft daylight", params);

    const fetchCall = (
      globalThis.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "Natural portrait with soft daylight",
      workflow: "realistic_persona",
      workflow_name: "realistic_persona",
      age: 34,
      gender: "woman",
      ethnicity: "latina",
      wardrobe: "linen blazer",
      expression: "calm smile",
      background: "sunlit studio",
      output_type: "editorial",
    });
  });

  it("includes image_url when a realistic persona reference face is provided", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "persona-face", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    const referenceFaceUrl = "data:image/png;base64,ZmFrZS1mYWNl";

    await submitGenerate("Natural portrait", {
      workflow_name: "realistic_persona",
      age: 34,
      image_url: referenceFaceUrl,
    });

    const fetchCall = (
      globalThis.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "Natural portrait",
      workflow: "realistic_persona",
      workflow_name: "realistic_persona",
      age: 34,
      image_url: referenceFaceUrl,
    });
  });

  it("omits empty persona controls from the request payload", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "persona-defaults", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await submitGenerate("Natural portrait", {
      workflow_name: "realistic_persona",
      age: 34,
      gender: "",
      ethnicity: "",
      wardrobe: "linen blazer",
      expression: "",
      background: "",
      output_type: "",
    } as unknown as GenerationParameters);

    const fetchCall = (
      globalThis.fetch as ReturnType<typeof vi.fn>
    ).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "Natural portrait",
      workflow: "realistic_persona",
      workflow_name: "realistic_persona",
      age: 34,
      wardrobe: "linen blazer",
    });
    expect(callBody).not.toHaveProperty("gender");
    expect(callBody).not.toHaveProperty("ethnicity");
    expect(callBody).not.toHaveProperty("expression");
    expect(callBody).not.toHaveProperty("background");
    expect(callBody).not.toHaveProperty("output_type");
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
