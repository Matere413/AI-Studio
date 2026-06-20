// @vitest-environment jsdom

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GenerationParameters } from "../api/types";
import {
  DEFAULT_WS_MAX_RETRIES,
  DEFAULT_WS_RETRY_DELAY,
  connectWebSocket,
  getWsUrl,
  submitGenerate,
} from "../api/client";
import { useGenerationStore } from "../stores/generationStore";
import { useGenerationFlow } from "./useGenerationFlow";

vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn((jobId: string) => `/api/ws/generate/${jobId}`),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(),
  DEFAULT_WS_MAX_RETRIES: 3,
  DEFAULT_WS_RETRY_DELAY: 1000,
}));

const mockSubmitGenerate = vi.mocked(submitGenerate);
const mockGetWsUrl = vi.mocked(getWsUrl);
const mockConnectWebSocket = vi.mocked(connectWebSocket);

function resetStore() {
  useGenerationStore.setState({
    prompt: "",
    parameters: {},
    currentJob: null,
    terminalEvent: null,
    generationState: "idle",
    sessionHistory: [],
    referenceFaceUrl: null,
    referenceGallery: [],
    validationErrors: {},
    errorMessage: null,
    _wsCleanup: null,
  });
}

async function startFlow(
  prompt = "A cinematic product photo",
  parameters: GenerationParameters = { workflow_name: "flux2_txt2img" }
) {
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

  it("submits a prompt and starts the websocket lifecycle", async () => {
    const cleanup = vi.fn();
    mockConnectWebSocket.mockReturnValue(cleanup);

    await startFlow("A cinematic product photo", {
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });

    expect(mockSubmitGenerate).toHaveBeenCalledWith("A cinematic product photo", {
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });
    expect(mockGetWsUrl).toHaveBeenCalledWith("job-123");
    expect(mockConnectWebSocket).toHaveBeenCalledWith(
      "/api/ws/generate/job-123",
      expect.objectContaining({
        maxRetries: DEFAULT_WS_MAX_RETRIES,
        retryDelay: DEFAULT_WS_RETRY_DELAY,
      })
    );
    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({ generationState: "booting", _wsCleanup: cleanup })
    );
    expect(useGenerationStore.getState().currentJob?.job_id).toBe("job-123");
  });

  it("adds the reference image to editing submissions", async () => {
    useGenerationStore.setState({
      referenceFaceUrl: "data:image/png;base64,ZmFrZS1lZGl0aW5n",
    });

    await startFlow("Edit this photo", {
      workflow_name: "flux2_editing",
    });

    expect(mockSubmitGenerate).toHaveBeenCalledWith(
      "Edit this photo",
      expect.objectContaining({
        workflow_name: "flux2_editing",
        image_base64: "data:image/png;base64,ZmFrZS1lZGl0aW5n",
      })
    );
  });

  it("cancels an in-flight generation by running websocket cleanup", async () => {
    const cleanup = vi.fn();
    mockConnectWebSocket.mockReturnValue(cleanup);
    const { result } = await startFlow("Cancel this job", {
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });

    act(() => {
      result.current.cancel();
    });

    expect(cleanup).toHaveBeenCalledTimes(1);
    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "idle",
        currentJob: null,
        _wsCleanup: null,
      })
    );
  });

  it("maps retry exhaustion to the connection lost error", async () => {
    let wsOptions: Parameters<typeof mockConnectWebSocket>[1] | undefined;
    mockConnectWebSocket.mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });

    await startFlow("Retry test", {
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });

    act(() => {
      wsOptions?.onExhausted?.();
    });

    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "error",
        errorMessage: "Connection lost — please try again",
      })
    );
  });
});
