// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "./page";

describe("view2 route smoke test", () => {
  it("renders the entry page without crashing", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: /generative ai studio/i })
    ).toBeTruthy();
  });
});
