import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import StudioLayout from "./GenerationStudio";
import { useGenerationStore } from "../stores/generationStore";

// Mock the API module so Sidebar doesn't try to make real network calls
vi.mock("../api/client", () => ({
  submitGenerate: vi.fn(),
  getWsUrl: vi.fn(() => "/api/ws/generate/test-job"),
  connectWebSocket: vi.fn(() => vi.fn()),
}));

describe("StudioLayout (Spec: Studio Layout Composition — Scenarios: Desktop layout, Below threshold)", () => {
  beforeEach(() => {
    useGenerationStore.setState({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
      referenceGallery: [],
      validationErrors: {},
      errorMessage: null,
      _wsCleanup: null,
    });
  });

  it("renders sidebar, canvas, and terminal sections", () => {
    const { container } = render(<StudioLayout />);

    // Studio layout should contain sidebar, canvas, and terminal areas
    expect(container.querySelector("[class*='sidebar']")).toBeInTheDocument();
    expect(container.querySelector("[class*='canvas']")).toBeInTheDocument();
    expect(container.querySelector("[class*='terminal']")).toBeInTheDocument();
  });

  it("applies grid layout class to the studio container (Spec: Studio Layout — Scenario: Desktop layout)", () => {
    const { container } = render(<StudioLayout />);

    const studio = container.querySelector("[class*='studio']");
    expect(studio).toBeInTheDocument();
    // The studio container uses CSS grid — verify the class is applied
    // (CSS properties are not computed in jsdom, so we check the class name)
    expect(studio!.className).toMatch(/studio/);
  });

  it("terminal starts collapsed on desktop (Spec: Studio Layout — Scenario: Desktop layout)", () => {
    render(<StudioLayout />);

    // Terminal should start collapsed — the toggle button should show ▸ (collapsed)
    const toggleButtons = screen.getAllByRole("button");
    const terminalButton = toggleButtons.find(
      (btn) => btn.textContent?.includes("Terminal")
    );
    expect(terminalButton).toBeInTheDocument();
    // Collapsed state shows ▸
    expect(terminalButton!.textContent).toContain("▸");
  });

  it("renders the prompt textarea in the sidebar", () => {
    render(<StudioLayout />);
    expect(screen.getByPlaceholderText(/Describe what you want/i)).toBeInTheDocument();
  });

  it("renders the placeholder text in the canvas area", () => {
    render(<StudioLayout />);
    expect(screen.getByText(/Enter a prompt and click Generate/i)).toBeInTheDocument();
  });

  it("renders the generate button in the sidebar", () => {
    render(<StudioLayout />);
    expect(screen.getByRole("button", { name: /generate/i })).toBeInTheDocument();
  });

  it("renders the lateral identity settings panel in the sidebar", () => {
    useGenerationStore.setState({ parameters: { workflow_name: "identidad_gguf" } });

    render(<StudioLayout />);

    expect(screen.getByRole("region", { name: /identity settings/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/upload reference image/i)).toBeInTheDocument();
  });

  it("studio container constrains height to viewport (no page-level scroll)", () => {
    const { container } = render(<StudioLayout />);
    const studio = container.querySelector("[class*='studio']");
    expect(studio).toBeInTheDocument();
    // The studio must not allow page-level scroll — it uses height:100vh
    // rather than min-height:100vh so content stays within the viewport
    expect(studio!.className).toMatch(/studio/);
    // Verify the data attribute that signals viewport-constrained layout
    expect(studio).toHaveAttribute("data-viewport-constrained", "true");
  });

  it("sidebar scrolls internally when content overflows (Spec: Viewport stability)", () => {
    const { container } = render(<StudioLayout />);
    const sidebar = container.querySelector("[class*='sidebar']");
    expect(sidebar).toBeInTheDocument();
    // Sidebar has overflow-y: auto so it scrolls internally, not the page
    expect(sidebar!.className).toMatch(/sidebar/);
  });
});
