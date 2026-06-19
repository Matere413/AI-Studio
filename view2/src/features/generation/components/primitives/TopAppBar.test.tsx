import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TopAppBar } from "./TopAppBar";

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

describe("TopAppBar", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders inline tabs, actions, and status on desktop", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));

    render(
      <TopAppBar
        actions={<button type="button">Publish</button>}
        status="green"
        statusLabel="Ready"
        tabs={[
          { id: "overview", label: "Overview", active: true, onSelect: vi.fn() },
          { id: "assets", label: "Assets", onSelect: vi.fn() },
        ]}
      />
    );

    expect(screen.getByRole("button", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /assets/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(document.querySelector(".status-dot--green")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open navigation menu/i })).not.toBeInTheDocument();
  });

  it("shows a hamburger menu below 1024px and reveals tabs on demand", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(false));
    const onOverview = vi.fn();

    render(
      <TopAppBar
        actions={<button type="button">Publish</button>}
        status="amber"
        statusLabel="Idle"
        tabs={[{ id: "overview", label: "Overview", active: true, onSelect: onOverview }]}
      />
    );

    const menuButton = screen.getByRole("button", { name: /open navigation menu/i });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(menuButton);

    expect(menuButton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
  });
});
