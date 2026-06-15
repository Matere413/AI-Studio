import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { connectWebSocket, getWsUrl, submitGenerate } from "../api/client";
import type { GenerationParameters, WebSocketOptions } from "../api/types";
import { useGenerationStore } from "../stores/generationStore";
import { useGenerationFlow } from "./useGenerationFlow";

vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn((jobId: string) => `/api/ws/generate/${jobId}`),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(),
}));

const mockSubmitGenerate = vi.mocked(submitGenerate);
const mockGetWsUrl = vi.mocked(getWsUrl);
const mockConnectWebSocket = vi.mocked(connectWebSocket);

function resetStore() {
  useGenerationStore.setState({
    prompt: "",
    parameters: {},
    currentJob: null,
    generationState: "idle",
    sessionHistory: [],
    validationErrors: {},
    errorMessage: null,
    _wsCleanup: null,
  });
}

async function startFlow(prompt = "A cinematic product photo", parameters: GenerationParameters = { workflow_name: "txt2img" }) {
  const hook = renderHook(() => useGenerationFlow());
  act(() => {
    hook.result.current.setPrompt(prompt);
    hook.result.current.setParameters(parameters);
  });
  await act(async () => {
    await hook.result.current.generate();
  });
  return hook;
}

describe("useGenerationFlow", () => {
  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
    mockSubmitGenerate.mockResolvedValue({ job_id: "job-123", status: "queued" });
    mockConnectWebSocket.mockReturnValue(vi.fn());
  });

  it("submits the unchanged payload and starts the WebSocket lifecycle", async () => {
    const cleanup = vi.fn();
    mockConnectWebSocket.mockReturnValue(cleanup);

    await startFlow("A cinematic product photo", { workflow_name: "txt2img", checkpoint_url: "https://model.test/checkpoint.safetensors" });

    expect(mockSubmitGenerate).toHaveBeenCalledWith("A cinematic product photo", {
      workflow_name: "txt2img",
      checkpoint_url: "https://model.test/checkpoint.safetensors",
    });
    expect(mockGetWsUrl).toHaveBeenCalledWith("job-123");
    expect(mockConnectWebSocket).toHaveBeenCalledWith(
      "/api/ws/generate/job-123",
      expect.objectContaining({ maxRetries: 3 })
    );
    expect(useGenerationStore.getState()).toEqual(expect.objectContaining({ generationState: "connecting", _wsCleanup: cleanup }));
    expect(useGenerationStore.getState().currentJob?.job_id).toBe("job-123");
  });

  it("moves to error state with the submit failure message when generation submit rejects", async () => {
    mockSubmitGenerate.mockRejectedValueOnce(new Error("Queue is unavailable"));
    const { result } = renderHook(() => useGenerationFlow());

    act(() => {
      result.current.setPrompt("A cinematic product photo");
      result.current.setParameters({ workflow_name: "txt2img" });
    });
    await act(async () => {
      await result.current.generate();
    });

    expect(mockConnectWebSocket).not.toHaveBeenCalled();
    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({ generationState: "error", currentJob: null, errorMessage: "Queue is unavailable", _wsCleanup: null })
    );
  });

  it("forwards completed events so previews use /api/images/{jobId}", async () => {
    let wsOptions: WebSocketOptions | undefined;
    mockConnectWebSocket.mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });

    await startFlow("Gallery image", { workflow_name: "product_premium", format: "vertical" });

    act(() => {
      wsOptions?.onEvent({ event: "completed", job_id: "job-123", timestamp: "2026-06-14T21:10:00.000Z", result: { image_path: "backend/result.png" } });
    });

    expect(useGenerationStore.getState().generationState).toBe("done");
    expect(useGenerationStore.getState().sessionHistory[0]).toEqual(
      expect.objectContaining({
        id: "job-123",
        imagePath: "/api/images/job-123",
        prompt: "Gallery image",
      })
    );
  });

  it("maps retry exhaustion to the existing connection-lost error", async () => {
    let wsOptions: WebSocketOptions | undefined;
    mockConnectWebSocket.mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });

    await startFlow("Retry test", { workflow_name: "controlnet" });

    act(() => wsOptions?.onExhausted?.());

    expect(useGenerationStore.getState()).toEqual(expect.objectContaining({ generationState: "error", errorMessage: "Connection lost — please try again" }));
  });

  it("cancels an in-flight generation by running WebSocket cleanup", async () => {
    const cleanup = vi.fn();
    mockConnectWebSocket.mockReturnValue(cleanup);
    const { result } = await startFlow("Cancel this job", { workflow_name: "img2img" });

    act(() => result.current.cancel());

    expect(cleanup).toHaveBeenCalledTimes(1);
    expect(useGenerationStore.getState()).toEqual(expect.objectContaining({ generationState: "idle", currentJob: null, _wsCleanup: null }));
  });

  it("resets prompt, parameters, gallery history, and WebSocket cleanup", async () => {
    const cleanup = vi.fn();
    mockConnectWebSocket.mockReturnValue(cleanup);
    useGenerationStore.setState({
      sessionHistory: [{ id: "older-job", imagePath: "/api/images/older-job", prompt: "Older", parameters: { workflow_name: "txt2img" }, completedAt: "2026-06-14T21:00:00.000Z" }],
    });
    const { result } = await startFlow("Reset this job", { workflow_name: "txt2img" });

    act(() => result.current.reset());

    expect(cleanup).toHaveBeenCalledTimes(1);
    expect(useGenerationStore.getState()).toEqual(expect.objectContaining({ prompt: "", parameters: {}, generationState: "idle", sessionHistory: [], _wsCleanup: null }));
  });

  it("does not submit when the prompt is blank or validation has errors", async () => {
    const { result } = renderHook(() => useGenerationFlow());

    await act(async () => result.current.generate());
    act(() => {
      result.current.setPrompt("Valid words");
      result.current.setParameters({});
    });
    await act(async () => result.current.generate());

    expect(mockSubmitGenerate).not.toHaveBeenCalled();
    expect(mockConnectWebSocket).not.toHaveBeenCalled();
  });
});
