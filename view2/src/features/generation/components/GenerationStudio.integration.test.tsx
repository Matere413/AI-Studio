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

function createMatchMedia(matches: boolean) {
  return vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

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
    useUiStore.getState().setAssetsDrawer("auto");
    useUiStore.getState().setAspectRatio("1:1");
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
    vi.stubGlobal("matchMedia", createMatchMedia(true));
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
    expect(document.querySelector(".status-dot--green")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /a refined editorial image/i })).toHaveAttribute(
      "src",
      "/api/images/job-int",
    );
  });

  it("updates turbo mode from the speed toggle before submitting", async () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));
    render(<GenerationStudio />);

    fireEvent.change(screen.getByRole("textbox", { name: /prompt/i }), {
      target: { value: "A slower premium render" },
    });
    fireEvent.click(screen.getByRole("button", { name: /quality/i }));
    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "A slower premium render",
        expect.objectContaining({ use_turbo: false }),
      );
    });
  });

  it("blocks identidad_gguf submission until a reference image is uploaded", async () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));
    render(<GenerationStudio />);

    fireEvent.change(screen.getByRole("textbox", { name: /prompt/i }), {
      target: { value: "Generate an identity-preserved portrait" },
    });
    fireEvent.change(screen.getByLabelText(/workflow/i), {
      target: { value: "identidad_gguf" },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Reference image required");
    expect(screen.getByRole("button", { name: /send prompt/i })).toBeDisabled();
    expect(submitGenerate).not.toHaveBeenCalled();
  });

  it("displays error banner when generation request fails", async () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));
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
    vi.stubGlobal("matchMedia", createMatchMedia(true));
    vi.stubGlobal("FileReader", MockFileReader);

    render(<GenerationStudio />);

    // Upload a file
    const input = screen.getByLabelText(/upload reference asset/i);
    const file = new File(["ref"], "face.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      const store = useGenerationStore.getState();
      expect(store.referenceFaceUrl).toBe("data:image/png;base64,ZmFrZQ==");
      expect(store.referenceGallery).toContain("data:image/png;base64,ZmFrZQ==");
      expect(screen.getByRole("button", { name: /remove face.png/i })).toBeInTheDocument();
    });
  });

  it("opens the assets drawer from mobile overlay mode", async () => {
    vi.stubGlobal("matchMedia", createMatchMedia(false));

    render(<GenerationStudio />);

    expect(screen.queryByRole("complementary", { name: /context assets/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /toggle assets/i }));

    await waitFor(() => {
      expect(screen.getByRole("complementary", { name: /context assets/i })).toHaveAttribute(
        "data-overlay",
        "true",
      );
    });
  });
});
