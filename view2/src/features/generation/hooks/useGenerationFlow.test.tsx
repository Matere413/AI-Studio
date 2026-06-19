import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { connectWebSocket, getWsUrl, submitGenerate } from "../api/client";
import type { WebSocketOptions } from "../api/types";
import { useGenerationStore } from "../stores/generationStore";
import { useGenerationFlow } from "./useGenerationFlow";

vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn((jobId: string) => `/api/ws/generate/${jobId}`),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(),
}));

describe("useGenerationFlow", () => {
  beforeEach(() => {
    useGenerationStore.getState().reset();
    vi.clearAllMocks();
    vi.mocked(submitGenerate).mockResolvedValue({
      job_id: "job-flow",
      status: "pending",
    });
    vi.mocked(connectWebSocket).mockReturnValue(vi.fn());
  });

  it("submits the store prompt and opens a WebSocket stream", async () => {
    const cleanup = vi.fn();
    vi.mocked(connectWebSocket).mockReturnValue(cleanup);
    const { result } = renderHook(() => useGenerationFlow());

    act(() => {
      result.current.setPrompt("A refined editorial render");
      result.current.setParameters({ workflow_name: "flux2_txt2img" });
    });
    await act(async () => {
      await result.current.generate();
    });

    expect(submitGenerate).toHaveBeenCalledWith("A refined editorial render", {
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });
    expect(getWsUrl).toHaveBeenCalledWith("job-flow");
    expect(connectWebSocket).toHaveBeenCalledWith(
      "/api/ws/generate/job-flow",
      expect.objectContaining({ maxRetries: 3 })
    );
    expect(useGenerationStore.getState()).toMatchObject({
      generationState: "booting",
      _wsCleanup: cleanup,
    });
  });

  it("adds selected reference assets to workflow-specific submissions", async () => {
    const { result } = renderHook(() => useGenerationFlow());

    act(() => {
      result.current.setPrompt("Preserve this face");
      result.current.setReferenceFaceUrl("data:image/png;base64,aWQ=");
      result.current.setParameters({ workflow_name: "identidad_gguf" });
    });
    await act(async () => {
      await result.current.generate();
    });

    expect(submitGenerate).toHaveBeenCalledWith("Preserve this face", {
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,aWQ=",
    });
  });

  it("dispatches WebSocket events into the store", async () => {
    let wsOptions: WebSocketOptions | undefined;
    vi.mocked(connectWebSocket).mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });
    const { result } = renderHook(() => useGenerationFlow());

    act(() => {
      result.current.setPrompt("Streamed output");
      result.current.setParameters({ workflow_name: "flux2_txt2img" });
    });
    await act(async () => {
      await result.current.generate();
    });
    act(() => {
      wsOptions?.onEvent({
        event: "completed",
        job_id: "job-flow",
        timestamp: "2026-06-18T00:00:00.000Z",
      });
    });

    expect(useGenerationStore.getState().generationState).toBe("done");
    expect(useGenerationStore.getState().sessionHistory[0].imagePath).toBe(
      "/api/images/job-flow"
    );
  });

  it("does not submit invalid form state and maps failures to the store", async () => {
    const { result } = renderHook(() => useGenerationFlow());

    await act(async () => {
      await result.current.generate();
    });
    expect(submitGenerate).not.toHaveBeenCalled();

    vi.mocked(submitGenerate).mockRejectedValueOnce(new Error("Queue down"));
    act(() => {
      result.current.setPrompt("Valid prompt");
      result.current.setParameters({ workflow_name: "flux2_txt2img" });
    });
    await act(async () => {
      await result.current.generate();
    });

    expect(useGenerationStore.getState()).toMatchObject({
      generationState: "error",
      errorMessage: "Queue down",
    });
  });

  it("maps retry exhaustion to a connection-lost error", async () => {
    let wsOptions: WebSocketOptions | undefined;
    vi.mocked(connectWebSocket).mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });
    const { result } = renderHook(() => useGenerationFlow());

    act(() => {
      result.current.setPrompt("Retry me");
      result.current.setParameters({ workflow_name: "flux2_txt2img" });
    });
    await act(async () => {
      await result.current.generate();
    });
    act(() => wsOptions?.onExhausted?.());

    expect(useGenerationStore.getState()).toMatchObject({
      generationState: "error",
      errorMessage: "Connection lost — please try again",
    });
  });
});
