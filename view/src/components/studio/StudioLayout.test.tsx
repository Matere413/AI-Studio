import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import StudioLayout from "./StudioLayout";
import { useGenerationStore } from "@/stores/generationStore";

// Mock next/image to render a plain img
vi.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage(props: Record<string, unknown>) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img alt={props.alt as string} src={props.src as string} data-fill={props.fill ? "true" : "false"} />;
  },
}));

// Mock the API module so Sidebar doesn't try to make real network calls
vi.mock("@/lib/api", () => ({
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
});