// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import EventTerminal from "./EventTerminal";
import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

const resetStore = () =>
  useGenerationStore.setState({
    prompt: "",
    parameters: {},
    currentJob: null,
    terminalEvent: null,
    generationState: "idle",
    sessionHistory: [],
    referenceFaceUrl: null,
    referenceGallery: [],
    errorMessage: null,
    validationErrors: {},
    _wsCleanup: null,
  });

describe("EventTerminal", () => {
  beforeEach(resetStore);

  it("shows a scrollable monospace log placeholder when idle", () => {
    render(<EventTerminal />);

    expect(screen.getByRole("log", { name: /generation events/i })).toHaveClass(styles.eventLog);
    expect(screen.getByText(/waiting for generation events/i)).toBeInTheDocument();
  });

  it("lists streamed events with progress", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-1",
        status: "generating",
        progress: 75,
        events: [
          { event: "booting_server", job_id: "job-1", timestamp: "2026-06-20T00:00:00Z" },
          {
            event: "progress",
            job_id: "job-1",
            timestamp: "2026-06-20T00:00:05Z",
            progress: 75,
            message: "Halfway there",
          },
        ],
      },
    });

    render(<EventTerminal />);

    expect(screen.getByText(/booting_server/i)).toBeInTheDocument();
    expect(screen.getByText(/halfway there/i)).toBeInTheDocument();
    expect(screen.getByText(/75%/i)).toBeInTheDocument();
  });

  it("keeps the terminal completion event visible after the job clears", () => {
    useGenerationStore.getState().startConnecting("job-2");
    useGenerationStore.getState().addEvent({
      event: "completed",
      job_id: "job-2",
      timestamp: "2026-06-20T00:00:10Z",
      result: { image_path: "/api/images/job-2" },
    });

    expect(useGenerationStore.getState().currentJob).toBeNull();

    render(<EventTerminal />);

    expect(screen.getByRole("log", { name: /generation events/i })).toHaveTextContent(/completed/i);
  });

  it("keeps the terminal error event visible after the job clears", () => {
    useGenerationStore.getState().startConnecting("job-3");
    useGenerationStore.getState().addEvent({
      event: "error",
      job_id: "job-3",
      timestamp: "2026-06-20T00:00:11Z",
      error: { code: "comfyui_execution_failed", detail: "Boom" },
    });

    expect(useGenerationStore.getState().currentJob).toBeNull();

    render(<EventTerminal />);

    expect(screen.getByRole("log", { name: /generation events/i })).toHaveTextContent(/error/i);
  });
});
