import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GenerationStudio } from "./GenerationStudio";

describe("GenerationStudio", () => {
  it("composes the 3-panel studio shell", () => {
    render(<GenerationStudio />);

    expect(screen.getByTestId("generation-studio")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /agent chat/i })).toBeInTheDocument();
    expect(screen.getByRole("main", { name: /studio workspace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /toggle assets/i })).toBeInTheDocument();
  });

  it("opens and closes the right assets drawer without leaving the shell", () => {
    render(<GenerationStudio />);

    const toggle = screen.getByRole("button", { name: /toggle assets/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
