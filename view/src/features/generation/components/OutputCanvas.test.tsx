import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Canvas from "./OutputCanvas";
import { useGenerationStore } from "../stores/generationStore";

describe("Canvas (Spec: Generation State Machine; Spec: Cold Start; Spec: Modal Cold Start Handling)", () => {
  beforeEach(() => {
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
  });

  it("shows placeholder when idle with no history", () => {
    render(<Canvas />);
    expect(screen.getByText(/Enter a prompt and click Generate/i)).toBeInTheDocument();
  });

  it("shows connecting status badge when connecting (Spec: State Machine — Scenario: Full lifecycle)", () => {
    useGenerationStore.setState({
      generationState: "connecting",
      currentJob: {
        job_id: "job-1",
        status: "connecting",
        progress: null,
        events: [],
      },
    });

    render(<Canvas />);
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });

  it("shows generating status badge during generating", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-2",
        status: "running",
        progress: 0.5,
        events: [],
      },
    });

    render(<Canvas />);
    expect(screen.getByText("Generating")).toBeInTheDocument();
    // Progress percentage appears in both status row and progress bar
    const progressElements = screen.getAllByText("50%");
    expect(progressElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows indeterminate progress during cold start (Spec: Cold Start — Scenario: Cold start delay)", () => {
    useGenerationStore.setState({
      generationState: "connecting",
      currentJob: {
        job_id: "job-cold",
        status: "connecting",
        progress: null,
        events: [],
      },
    });

    const { container } = render(<Canvas />);
    // When in connecting state with null progress, no percentage should appear
    expect(container.textContent).not.toMatch(/\d+%/);
    // The "Connecting..." badge should be present
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });

  it("shows determinate progress when progress is available (Spec: Cold Start — Scenario: Becomes determinate)", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-det",
        status: "running",
        progress: 0.75,
        events: [{ event: "running" as const, job_id: "job-det", timestamp: "2024-01-01T00:00:00Z", progress: 0.75 }],
      },
    });

    render(<Canvas />);
    // Progress percentage appears in both status row and progress bar
    const progressElements = screen.getAllByText("75%");
    expect(progressElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows completed image from session history when done", () => {
    useGenerationStore.setState({
      generationState: "done",
      currentJob: null,
      sessionHistory: [
        {
          id: "job-done",
          imagePath: "/api/images/job-done",
          prompt: "A sunset",
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T00:01:00Z",
        },
      ],
    });

    render(<Canvas />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
    const image = screen.getByRole("img");
    expect(image).toHaveAttribute("src", "/api/images/job-done");
  });

  it("shows error banner on error state (Spec: State Machine — Scenario: Failure)", () => {
    useGenerationStore.setState({
      generationState: "error",
      errorMessage: "Connection lost — please try again",
      currentJob: null,
    });

    render(<Canvas />);
    expect(screen.getByText(/Connection lost/)).toBeInTheDocument();
  });
});
