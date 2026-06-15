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

  it("renders persona controls when realistic_persona workflow is selected", () => {
    useGenerationStore.setState({
      prompt: "Natural editorial portrait",
      parameters: {
        workflow_name: "realistic_persona",
        age: 34,
        gender: "woman",
        ethnicity: "latina",
        wardrobe: "linen blazer",
        expression: "soft smile",
        background: "warm studio",
        output_type: "portrait",
      } as never,
      validationErrors: {},
    });

    renderPromptPanel();

    expect(screen.getByRole("button", { name: /persona/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/age/i)).toHaveValue("34");
    expect(screen.getByLabelText(/gender/i)).toHaveValue("woman");
    expect(screen.getByLabelText(/ethnicity/i)).toHaveValue("latina");
    expect(screen.getByLabelText(/wardrobe/i)).toHaveValue("linen blazer");
    expect(screen.getByLabelText(/expression/i)).toHaveValue("soft smile");
    expect(screen.getByLabelText(/background/i)).toHaveValue("warm studio");
    expect(screen.getByRole("radio", { name: /portrait/i })).toBeChecked();
  });

  it("hides model and technical controls for the persona workflow", () => {
    useGenerationStore.setState({
      prompt: "Natural editorial portrait",
      parameters: { workflow_name: "realistic_persona" } as never,
      validationErrors: {},
    });

    renderPromptPanel();

    expect(screen.queryByLabelText(/checkpoint url/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/lora url/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/cfg/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/sampler/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/steps/i)).not.toBeInTheDocument();
  });

  it("submits filled persona controls with the prompt", async () => {
    useGenerationStore.setState({
      prompt: "Natural editorial portrait",
      parameters: { workflow_name: "realistic_persona" } as never,
      validationErrors: {},
    });

    renderPromptPanel();

    fireEvent.change(screen.getByLabelText(/age/i), { target: { value: "48" } });
    fireEvent.change(screen.getByLabelText(/gender/i), { target: { value: "man" } });
    fireEvent.change(screen.getByLabelText(/ethnicity/i), { target: { value: "east_asian" } });
    fireEvent.change(screen.getByLabelText(/wardrobe/i), { target: { value: "wool coat" } });
    fireEvent.change(screen.getByLabelText(/expression/i), { target: { value: "thoughtful" } });
    fireEvent.change(screen.getByLabelText(/background/i), { target: { value: "city street" } });
    fireEvent.click(screen.getByRole("radio", { name: /editorial/i }));
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "Natural editorial portrait",
        expect.objectContaining({
          workflow_name: "realistic_persona",
          age: 48,
          gender: "man",
          ethnicity: "east_asian",
          wardrobe: "wool coat",
          expression: "thoughtful",
          background: "city street",
          output_type: "editorial",
        })
      );
    });
  });

  it("does not submit empty strings when persona selects return to Default", async () => {
    useGenerationStore.setState({
      prompt: "Natural editorial portrait",
      parameters: {
        workflow_name: "realistic_persona",
        gender: "woman",
        ethnicity: "latina",
      } as never,
      validationErrors: {},
    });

    renderPromptPanel();

    fireEvent.change(screen.getByLabelText(/gender/i), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalled();
    });

    const submittedParams = vi.mocked(submitGenerate).mock.calls[0][1];
    expect(submittedParams).toMatchObject({
      workflow_name: "realistic_persona",
      ethnicity: "latina",
    });
    expect(submittedParams).not.toHaveProperty("gender");
  });
});
