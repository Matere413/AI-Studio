import { describe, it, expect, vi, beforeEach } from "vitest";
import { submitGenerate, getWsUrl } from "./api";

describe("submitGenerate (Spec: API Integration — Scenario: Flux 2 + Identity)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("posts flux2_txt2img with use_turbo defaulting to true", async () => {
    const mockResponse = { job_id: "abc-123", status: "pending" };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mockResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await submitGenerate("A fiery sunset", {
      workflow_name: "flux2_txt2img",
    });

    expect(result).toEqual({ job_id: "abc-123", status: "pending" });
    const fetchCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "A fiery sunset",
      workflow: "flux2_txt2img",
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });
  });

  it("posts flux2_editing with image_base64", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "edit-456", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    const imageBase64 = "data:image/png;base64,ZmFrZS1lZGl0";

    await submitGenerate("Edit this photo", {
      workflow_name: "flux2_editing",
      use_turbo: true,
      image_base64: imageBase64,
    });

    const fetchCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "Edit this photo",
      workflow: "flux2_editing",
      workflow_name: "flux2_editing",
      use_turbo: true,
      image_base64: imageBase64,
    });
  });

  it("posts identidad_gguf with image_url and dimensions", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "iden-789", status: "pending" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await submitGenerate("Preserve this identity", {
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,ZmFrZQ==",
      width: 768,
      height: 1024,
      seed: 42,
    });

    const fetchCall = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const callBody = JSON.parse(requestInit.body as string);
    expect(callBody).toMatchObject({
      prompt: "Preserve this identity",
      workflow: "identidad_gguf",
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,ZmFrZQ==",
      width: 768,
      height: 1024,
      seed: 42,
    });
  });

  it("throws on non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 })
    );

    await expect(
      submitGenerate("test", { workflow_name: "flux2_txt2img" })
    ).rejects.toThrow("Generation request failed: 400");
  });

  it("throws on network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(
      new TypeError("Failed to fetch")
    );

    await expect(
      submitGenerate("test", { workflow_name: "flux2_txt2img" })
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