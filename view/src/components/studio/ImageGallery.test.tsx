import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ImageGallery, { truncatePrompt, MAX_PROMPT_LENGTH } from "./ImageGallery";
import { useGenerationStore } from "@/stores/generationStore";

// Mock next/image to render a plain img
vi.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage(props: Record<string, unknown>) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img alt={props.alt as string} src={props.src as string} data-fill={props.fill ? "true" : "false"} />;
  },
}));

describe("truncatePrompt (Spec: Session History Gallery — Scenario: Populated gallery)", () => {
  it("returns prompt unchanged if under max length", () => {
    expect(truncatePrompt("A fiery sunset")).toBe("A fiery sunset");
  });

  it("returns prompt unchanged if exactly at max length", () => {
    const promptAtMax = "x".repeat(MAX_PROMPT_LENGTH);
    expect(truncatePrompt(promptAtMax)).toBe(promptAtMax);
  });

  it("truncates and appends ellipsis when over max length", () => {
    const promptOverMax = "x".repeat(MAX_PROMPT_LENGTH + 20);
    const result = truncatePrompt(promptOverMax);
    expect(result).toBe("x".repeat(MAX_PROMPT_LENGTH) + "...");
  });

  it("truncates at exactly MAX_PROMPT_LENGTH characters before ellipsis", () => {
    const prompt200 = "a".repeat(200);
    const result = truncatePrompt(prompt200);
    expect(result.length).toBe(MAX_PROMPT_LENGTH + 3);
  });

  it("handles empty string", () => {
    expect(truncatePrompt("")).toBe("");
  });
});

describe("ImageGallery render (Spec: Session History Gallery — Scenarios: Populated gallery, Empty gallery)", () => {
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

  it("shows empty state placeholder when no history (Spec: Session History Gallery — Scenario: Empty gallery)", () => {
    render(<ImageGallery />);
    expect(screen.getByText("No generations yet")).toBeInTheDocument();
  });

  it("renders gallery items from session history (Spec: Session History Gallery — Scenario: Populated gallery)", () => {
    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-1",
          imagePath: "/api/images/job-1",
          prompt: "First prompt",
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T12:01:00Z",
        },
        {
          id: "job-2",
          imagePath: "/api/images/job-2",
          prompt: "Second prompt",
          parameters: { workflow_name: "img2img" as const },
          completedAt: "2024-01-01T12:02:00Z",
        },
        {
          id: "job-3",
          imagePath: "/api/images/job-3",
          prompt: "Third prompt",
          parameters: { workflow_name: "controlnet" as const },
          completedAt: "2024-01-01T12:03:00Z",
        },
      ],
    });

    render(<ImageGallery />);

    expect(screen.getByText("Session History")).toBeInTheDocument();
    expect(screen.getByText("First prompt")).toBeInTheDocument();
    expect(screen.getByText("Second prompt")).toBeInTheDocument();
    expect(screen.getByText("Third prompt")).toBeInTheDocument();
  });

  it("renders newest first in session history", () => {
    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-newer",
          imagePath: "/api/images/job-newer",
          prompt: "Newer generation",
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T12:02:00Z",
        },
        {
          id: "job-older",
          imagePath: "/api/images/job-older",
          prompt: "Older generation",
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T12:01:00Z",
        },
      ],
    });

    render(<ImageGallery />);

    const prompts = screen.getAllByText(/generation/);
    // Newest first: "Newer generation" should appear before "Older generation"
    expect(prompts[0]).toHaveTextContent("Newer generation");
    expect(prompts[1]).toHaveTextContent("Older generation");
  });

  it("truncates long prompts in gallery cards", () => {
    const longPrompt = "x".repeat(100);
    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-long",
          imagePath: "/api/images/job-long",
          prompt: longPrompt,
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T12:00:00Z",
        },
      ],
    });

    render(<ImageGallery />);

    // The truncated prompt should end with "..."
    const cardText = screen.getByText(/\.\.\.$/);
    expect(cardText).toBeInTheDocument();
  });

  it("renders images with correct src and alt attributes", () => {
    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-img",
          imagePath: "/api/images/job-img",
          prompt: "Test image",
          parameters: { workflow_name: "txt2img" as const },
          completedAt: "2024-01-01T12:00:00Z",
        },
      ],
    });

    render(<ImageGallery />);

    const images = screen.getAllByRole("img");
    expect(images.length).toBeGreaterThanOrEqual(1);
    // Find the gallery image (not the empty state)
    const galleryImage = images.find((img) => img.getAttribute("src") === "/api/images/job-img");
    expect(galleryImage).toBeDefined();
    expect(galleryImage!.getAttribute("alt")).toBe("Generated image for Test image");
  });
});
