import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GenerationStudio } from "./GenerationStudio";

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

describe("GenerationStudio", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("composes the studio shell with a mounted top app bar", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));

    render(<GenerationStudio />);

    expect(screen.getByTestId("generation-studio")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /primary tabs/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /^studio$/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /agent chat/i })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: /studio workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();
  });

  it("keeps the desktop drawer open by default and can close it explicitly", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));

    render(<GenerationStudio />);

    const toggle = screen.getByRole("button", { name: /toggle assets/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: /context assets/i })).not.toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});
