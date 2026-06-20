// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import TopAppBar from "./TopAppBar";

describe("TopAppBar", () => {
  it("renders disabled utility controls", () => {
    render(<TopAppBar />);

    for (const name of ["Export", "Publish", "Search", "Fullscreen"]) {
      const button = screen.getByRole("button", { name });
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAttribute("tabindex", "-1");
    }
  });

  it("keeps the studio title in the center column", () => {
    render(<TopAppBar />);

    expect(screen.getByRole("heading", { name: /generative ai studio/i })).toBeInTheDocument();
    expect(screen.getByRole("toolbar", { name: /studio top bar/i })).toBeInTheDocument();
  });
});
