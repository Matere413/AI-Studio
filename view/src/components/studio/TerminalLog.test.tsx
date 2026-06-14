import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TerminalLog from "./TerminalLog";
import { useGenerationStore } from "@/stores/generationStore";

describe("TerminalLog (Spec: Studio Layout — Scenario: Desktop layout; Spec: Cold Start — Scenario: Cold start delay)", () => {
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

  it("starts collapsed on desktop (Spec: Studio Layout — Scenario: Desktop layout)", () => {
    render(<TerminalLog />);
    // Terminal body should NOT be visible when collapsed
    const terminalBody = screen.queryByText(/Waiting for events/);
    expect(terminalBody).not.toBeInTheDocument();
  });

  it("can be expanded by clicking the toggle button", () => {
    render(<TerminalLog />);

    const toggleButton = screen.getByRole("button", { name: /terminal/i });
    fireEvent.click(toggleButton);

    // After expanding, terminal body should be visible
    expect(screen.getByText(/Waiting for events/)).toBeInTheDocument();
  });

  it("shows cold start message when expanded during connecting state (Spec: Cold Start — Scenario: Cold start delay)", () => {
    useGenerationStore.setState({
      generationState: "connecting",
      currentJob: {
        job_id: "job-cold",
        status: "connecting",
        progress: null,
        events: [],
      },
    });

    render(<TerminalLog />);

    // Expand the terminal
    const toggleButton = screen.getByRole("button", { name: /terminal/i });
    fireEvent.click(toggleButton);

    expect(screen.getByText(/Starting generation server/)).toBeInTheDocument();
  });

  it("shows cold start message during generating state with no events when expanded", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-gen",
        status: "running",
        progress: null,
        events: [],
      },
    });

    render(<TerminalLog />);
    const toggleButton = screen.getByRole("button", { name: /terminal/i });
    fireEvent.click(toggleButton);

    expect(screen.getByText(/Starting generation server/)).toBeInTheDocument();
  });

  it("displays event messages when expanded", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-events",
        status: "running",
        progress: 0.5,
        events: [
          { event: "running" as const, job_id: "job-events", timestamp: "2024-01-01T00:00:00Z", message: "Processing..." },
        ],
      },
    });

    render(<TerminalLog />);
    const toggleButton = screen.getByRole("button", { name: /terminal/i });
    fireEvent.click(toggleButton);

    expect(screen.getByText(/Processing/)).toBeInTheDocument();
  });
});