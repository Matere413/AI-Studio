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

describe("PromptPanel (Spec: Flux 2 Form Validation + Workflow Controls)", () => {
  beforeEach(() => {
    useGenerationStore.setState({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
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
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    renderPromptPanel();
    const generateBtn = screen.getByRole("button", { name: /generate/i });
    expect(generateBtn).not.toBeDisabled();
  });

  it("renders three Flux 2 + Identity workflow chips", () => {
    renderPromptPanel();
    expect(screen.getByRole("button", { name: /flux 2 t2i/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /flux 2 edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /identity/i })).toBeInTheDocument();
  });

  it("does not render legacy workflow chips", () => {
    renderPromptPanel();
    expect(screen.queryByRole("button", { name: /qwen/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /txt → img/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /img → img/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /controlnet/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /product/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /persona/i })).not.toBeInTheDocument();
  });

  it("shows turbo toggle when Flux 2 txt2img is selected (Spec: Flux 2 Turbo Control)", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_txt2img" },
      validationErrors: {},
    });
    renderPromptPanel();
    expect(screen.getByLabelText(/turbo mode/i)).toBeInTheDocument();
  });

  it("shows turbo toggle when Flux 2 editing is selected", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    renderPromptPanel();
    expect(screen.getByLabelText(/turbo mode/i)).toBeInTheDocument();
  });

  it("hides turbo toggle when identidad_gguf is selected (layout stability: rendered but collapsed)", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "identidad_gguf" },
      referenceFaceUrl: "data:image/png;base64,ZmFrZQ==",
      validationErrors: {},
    });
    renderPromptPanel();
    // Turbo section persists in DOM for layout stability but is hidden
    const turboSection = screen.getByTestId("turbo-section");
    expect(turboSection).toHaveAttribute("data-hidden", "true");
    expect(turboSection).toHaveAttribute("aria-hidden", "true");
  });

  it("defaults turbo to on and toggles to off on click", () => {
    useGenerationStore.getState().setPrompt("Test prompt");
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    renderPromptPanel();

    const turboBtn = screen.getByText(/turbo on/i).closest("button")!;
    expect(turboBtn).toBeInTheDocument();

    fireEvent.click(turboBtn);
    expect(screen.getByText(/turbo off/i)).toBeInTheDocument();
  });

  it("shows reference image upload for flux2_editing workflow", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    renderPromptPanel();
    expect(screen.getByLabelText(/reference image/i)).toBeInTheDocument();
  });

  it("shows reference image upload for identidad_gguf workflow", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "identidad_gguf" },
      validationErrors: {},
    });
    renderPromptPanel();
    expect(screen.getByLabelText(/reference image/i)).toBeInTheDocument();
  });

  it("hides reference image upload for flux2_txt2img workflow (layout stability: rendered but collapsed)", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_txt2img" },
      validationErrors: {},
    });
    renderPromptPanel();
    // Reference section persists in DOM for layout stability but is hidden
    const referenceSection = screen.getByTestId("reference-section");
    expect(referenceSection).toHaveAttribute("data-hidden", "true");
    expect(referenceSection).toHaveAttribute("aria-hidden", "true");
  });

  it("stores a valid PNG reference image as a data URI and shows preview", async () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    const imageFile = new File(["fake image content"], "face.png", {
      type: "image/png",
    });

    renderPromptPanel();
    fireEvent.change(screen.getByLabelText(/reference image/i), {
      target: { files: [imageFile] },
    });

    await waitFor(() => {
      expect(useGenerationStore.getState().referenceFaceUrl).toMatch(
        /^data:image\/png;base64,/
      );
    });
  });

  it("rejects unsupported reference image formats with an inline error", async () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    const gifFile = new File(["fake gif"], "face.gif", { type: "image/gif" });

    renderPromptPanel();
    fireEvent.change(screen.getByLabelText(/reference image/i), {
      target: { files: [gifFile] },
    });

    expect(
      await screen.findByText("Only PNG and JPEG images are accepted")
    ).toBeInTheDocument();
  });

  it("rejects reference images over 10MB with an inline error", async () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    const oversizedFile = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "large.jpg", {
      type: "image/jpeg",
    });

    renderPromptPanel();
    fireEvent.change(screen.getByLabelText(/reference image/i), {
      target: { files: [oversizedFile] },
    });

    expect(await screen.findByText("Image must be under 10MB")).toBeInTheDocument();
  });

  it("removes a stored reference image when the remove button is clicked", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      referenceFaceUrl: "data:image/jpeg;base64,ZmFrZS1lZGl0",
      validationErrors: {},
    });

    renderPromptPanel();
    fireEvent.click(screen.getByRole("button", { name: /remove reference image/i }));

    expect(useGenerationStore.getState().referenceFaceUrl).toBeNull();
  });

  it("disables inputs during generating state (Spec: State Machine — Scenario: Full lifecycle)", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_txt2img", use_turbo: true },
      generationState: "generating",
      currentJob: {
        job_id: "job-active",
        status: "running",
        progress: 0.3,
        events: [],
      },
      validationErrors: {},
    });

    renderPromptPanel();
    const textarea = screen.getByPlaceholderText(/Describe what you want/i);
    expect(textarea).toBeDisabled();

    const workflowBtns = screen.getAllByRole("button", { name: /flux|identity/i });
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
      parameters: { workflow_name: "invalid" as unknown as "flux2_txt2img" },
      validationErrors: { parameters: "Invalid workflow" },
    });
    renderPromptPanel();

    expect(screen.getByText("Invalid workflow")).toBeInTheDocument();
  });

  it("submits flux2_txt2img workflow with prompt and use_turbo", async () => {
    useGenerationStore.setState({
      prompt: "A cinematic photo",
      parameters: { workflow_name: "flux2_txt2img", use_turbo: true },
      validationErrors: {},
    });

    renderPromptPanel();
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "A cinematic photo",
        expect.objectContaining({
          workflow_name: "flux2_txt2img",
          use_turbo: true,
        })
      );
    });
  });

  it("submits flux2_editing workflow with image_base64 from reference image", async () => {
    const editingBase64 = "data:image/png;base64,ZmFrZS1lZGl0";
    useGenerationStore.setState({
      prompt: "Edit this photo",
      parameters: { workflow_name: "flux2_editing", use_turbo: true },
      referenceFaceUrl: editingBase64,
      validationErrors: {},
    });

    renderPromptPanel();
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "Edit this photo",
        expect.objectContaining({
          workflow_name: "flux2_editing",
          use_turbo: true,
          image_base64: editingBase64,
        })
      );
    });
  });

  it("submits identidad_gguf workflow with image_url from reference image", async () => {
    const referenceFaceUrl = "data:image/png;base64,ZmFrZS1mYWNl";
    useGenerationStore.setState({
      prompt: "Identity portrait",
      parameters: { workflow_name: "identidad_gguf" },
      referenceFaceUrl,
      validationErrors: {},
    });

    renderPromptPanel();
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));

    await waitFor(() => {
      expect(submitGenerate).toHaveBeenCalledWith(
        "Identity portrait",
        expect.objectContaining({
          workflow_name: "identidad_gguf",
          image_url: referenceFaceUrl,
        })
      );
    });
  });

  // PR4: Layout stability tests — panels must not shift when switching workflows
  it("reserves space for turbo section even when hidden (no layout shift on workflow switch)", () => {
    // When identidad_gguf is selected, turbo toggle is visually hidden
    // but the section container persists to maintain layout stability
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "identidad_gguf" },
      validationErrors: {},
    });
    renderPromptPanel();

    // The turbo section wrapper should exist in the DOM even when hidden
    const turboSection = screen.getByTestId("turbo-section");
    expect(turboSection).toBeInTheDocument();
    // It should be marked as inert/hidden for accessibility
    expect(turboSection).toHaveAttribute("data-hidden", "true");
  });

  it("reserves space for reference image section even when hidden (no layout shift)", () => {
    // When flux2_txt2img is selected, reference image section is hidden
    // but the container persists
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_txt2img" },
      validationErrors: {},
    });
    renderPromptPanel();

    const referenceSection = screen.getByTestId("reference-section");
    expect(referenceSection).toBeInTheDocument();
    expect(referenceSection).toHaveAttribute("data-hidden", "true");
  });

  it("shows turbo section without data-hidden when flux2_txt2img is selected", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_txt2img" },
      validationErrors: {},
    });
    renderPromptPanel();

    const turboSection = screen.getByTestId("turbo-section");
    expect(turboSection).toBeInTheDocument();
    expect(turboSection).not.toHaveAttribute("data-hidden");
  });

  it("shows reference section without data-hidden when flux2_editing is selected", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    renderPromptPanel();

    const referenceSection = screen.getByTestId("reference-section");
    expect(referenceSection).toBeInTheDocument();
    expect(referenceSection).not.toHaveAttribute("data-hidden");
  });

  // Triangulate: workflow switching toggles section visibility
  it("both turbo and reference sections are visible when flux2_editing is selected", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "flux2_editing" },
      validationErrors: {},
    });
    renderPromptPanel();

    expect(screen.getByTestId("turbo-section")).not.toHaveAttribute("data-hidden");
    expect(screen.getByTestId("reference-section")).not.toHaveAttribute("data-hidden");
  });

  it("only reference section is visible when identidad_gguf is selected (turbo hidden)", () => {
    useGenerationStore.setState({
      prompt: "Test prompt",
      parameters: { workflow_name: "identidad_gguf" },
      validationErrors: {},
    });
    renderPromptPanel();

    expect(screen.getByTestId("turbo-section")).toHaveAttribute("data-hidden", "true");
    expect(screen.getByTestId("reference-section")).not.toHaveAttribute("data-hidden");
  });
});