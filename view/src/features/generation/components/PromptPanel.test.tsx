import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import PromptPanel from "./PromptPanel";
import { useGenerationFlow } from "../hooks/useGenerationFlow";
import { useGenerationStore } from "../stores/generationStore";
import { submitGenerate } from "../api/client";

// Mock the API module so Sidebar doesn't try to make real network calls
vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn(() => "/api/ws/generate/test-job"),
  getImageUrl: vi.fn((jobId: string) => `/api/images/${jobId}`),
  connectWebSocket: vi.fn(() => vi.fn()),
}));

function PromptPanelHarness() {
  const flow = useGenerationFlow();
  return <PromptPanel flow={flow} />;
}

function renderPromptPanel() {
  return render(<PromptPanelHarness />);
}

describe("Sidebar (Spec: Form Validation — Scenarios: Empty prompt, Exceeds limit, Invalid parameter; Spec: Generation State Machine)", () => {
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
    vi.clearAllMocks();
  });

  it("disables Generate button when prompt is empty (Spec: Form Validation — Scenario: Empty prompt)", () => {
    renderPromptPanel();
    const generateBtn = screen.getByRole("button", { name: /generate/i });
    expect(generateBtn).toBeDisabled();
  });

  it("disables Generate button when prompt is whitespace only", () => {
    useGenerationStore.getState().setPrompt("   ");
    renderPromptPanel();
    const generateBtn = screen.getByRole("button", { name: /generate/i });
    expect(generateBtn).toBeDisabled();
  });

  it("shows validation error for empty prompt (Spec: Form Validation — Scenario: Empty prompt)", () => {
    useGenerationStore.getState().setPrompt("");
    renderPromptPanel();
    expect(screen.getByText("Prompt is required")).toBeInTheDocument();
  });

  it("shows validation error for prompt exceeding 1000 chars (Spec: Form Validation — Scenario: Exceeds limit)", () => {
    useGenerationStore.getState().setPrompt("x".repeat(1001));
    renderPromptPanel();
    expect(screen.getByText("Prompt must be 1000 characters or less")).toBeInTheDocument();
  });

  it("shows validation error for missing workflow selection (Spec: Form Validation — Scenario: Invalid parameter)", () => {
    // Default parameters are empty — no workflow selected
    useGenerationStore.getState().setParameters({});
    renderPromptPanel();
    expect(screen.getByText("Please select a workflow")).toBeInTheDocument();
  });

  it("disables Generate button when validation errors exist", () => {
    useGenerationStore.getState().setPrompt("");
    renderPromptPanel();
    const generateBtn = screen.getByRole("button", { name: /generate/i });
    expect(generateBtn).toBeDisabled();
  });

  it("enables Generate button when prompt is valid and workflow selected", () => {
    useGenerationStore.getState().setPrompt("A valid prompt");
    useGenerationStore.getState().setParameters({ workflow_name: "txt2img" });
    renderPromptPanel();
    const generateBtn = screen.getByRole("button", { name: /generate/i });
    expect(generateBtn).not.toBeDisabled();
  });

  it("disables inputs during generating state (Spec: State Machine — Scenario: Full lifecycle)", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-active",
        status: "running",
        progress: 0.3,
        events: [],
      },
    });

    renderPromptPanel();
    const textarea = screen.getByPlaceholderText(/Describe what you want/i);
    expect(textarea).toBeDisabled();

    const workflowBtns = screen.getAllByRole("button", { name: /TXT|IMG|ControlNet/i });
    workflowBtns.forEach((btn) => {
      expect(btn).toBeDisabled();
    });
  });

  it("shows Cancel button during running state", () => {
    useGenerationStore.setState({
      generationState: "generating",
      currentJob: {
        job_id: "job-active",
        status: "running",
        progress: 0.3,
        events: [],
      },
    });

    renderPromptPanel();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("shows character counter", () => {
    renderPromptPanel();
    expect(screen.getByText("0/1000")).toBeInTheDocument();
  });

  it("shows validation error for invalid workflow name", () => {
    useGenerationStore.setState({
      parameters: { workflow_name: "invalid" as unknown as "txt2img" },
      validationErrors: { parameters: "Invalid workflow" },
    });
    renderPromptPanel();

    expect(screen.getByText("Invalid workflow")).toBeInTheDocument();
  });

  it("renders product workflow controls without technical inputs", () => {
    useGenerationStore.setState({
      prompt: "Premium perfume bottle on a marble pedestal",
      parameters: {
        workflow_name: "product_premium" as unknown as "txt2img",
        format: "square",
      } as never,
    });

    renderPromptPanel();

    expect(screen.getByRole("button", { name: /product/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /square/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /vertical/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/checkpoint url/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/lora url/i)).not.toBeInTheDocument();
  });

  it("submits the product workflow payload with vertical format", async () => {
    useGenerationStore.setState({
      prompt: "Premium bottle in soft daylight",
      parameters: {
        workflow_name: "product_premium" as unknown as "txt2img",
        format: "square",
      } as never,
      validationErrors: {},
    });

    renderPromptPanel();

    fireEvent.click(screen.getByRole("button", { name: /product/i }));
    fireEvent.click(screen.getByRole("button", { name: /vertical/i }));
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "Premium bottle in soft daylight",
        expect.objectContaining({
          workflow_name: "product_premium",
          format: "vertical",
        })
      );
    });
  });
});
