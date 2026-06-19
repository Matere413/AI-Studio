import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WebSocketOptions } from "../api/types";
import { useGenerationStore } from "../stores/generationStore";
import { useUiStore } from "../stores/uiStore";

vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn((jobId: string) => `/api/ws/generate/${jobId}`),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(),
}));

import { connectWebSocket, submitGenerate } from "../api/client";
import { GenerationStudio } from "./GenerationStudio";

class MockFileReader {
  result: string | ArrayBuffer | null = null;
  onload: null | (() => void) = null;

  readAsDataURL(file: File) {
    this.result = `data:${file.type};base64,ZmFrZQ==`;
    this.onload?.();
  }
}

describe("GenerationStudio integration", () => {
  beforeEach(() => {
    useGenerationStore.getState().reset();
    useUiStore.getState().closeAssetsDrawer();
    vi.clearAllMocks();
    vi.mocked(submitGenerate).mockResolvedValue({
      job_id: "job-int",
      status: "pending",
    });
    vi.mocked(connectWebSocket).mockReturnValue(vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits prompt and reflects WS lifecycle in the canvas", async () => {
    let wsOptions: WebSocketOptions | undefined;
    vi.mocked(connectWebSocket).mockImplementation((_url, options) => {
      wsOptions = options;
      return vi.fn();
    });

    render(<GenerationStudio />);

    // Type prompt
    const textarea = screen.getByRole("textbox", { name: /prompt/i });
    fireEvent.change(textarea, { target: { value: "A refined editorial image" } });

    // Submit
    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    // Wait for async generate() to complete
    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "A refined editorial image",
        expect.objectContaining({ workflow_name: "flux2_txt2img" }),
      );
    });

    // Simulate generating event with progress
    act(() => {
      wsOptions?.onEvent({
        event: "generating",
        job_id: "job-int",
        timestamp: "2026-01-01T00:00:00Z",
        progress: 42,
      });
    });

    expect(screen.getByRole("status")).toHaveTextContent(/generating/i);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");

    // Simulate completed event
    act(() => {
      wsOptions?.onEvent({
        event: "completed",
        job_id: "job-int",
        timestamp: "2026-01-01T00:01:00Z",
      });
    });

    expect(screen.getByRole("status")).toHaveTextContent(/complete/i);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/api/images/job-int");
  });

  it("displays error banner when generation request fails", async () => {
    vi.mocked(submitGenerate).mockRejectedValueOnce(
      new Error("Backend unavailable"),
    );

    render(<GenerationStudio />);

    fireEvent.change(screen.getByRole("textbox", { name: /prompt/i }), {
      target: { value: "Trigger error" },
    });

    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Backend unavailable");
    });
  });

  it("wires asset uploads to the generation store reference face", async () => {
    vi.stubGlobal("FileReader", MockFileReader);

    render(<GenerationStudio />);

    // Open assets drawer
    fireEvent.click(screen.getByRole("button", { name: /toggle assets/i }));

    // Upload a file
    const input = screen.getByLabelText(/upload reference asset/i);
    const file = new File(["ref"], "face.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      const store = useGenerationStore.getState();
      expect(store.referenceFaceUrl).toBe("data:image/png;base64,ZmFrZQ==");
      expect(store.referenceGallery).toContain("data:image/png;base64,ZmFrZQ==");
    });
  });
});
