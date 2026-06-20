// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusDot from "./StatusDot";

describe("StatusDot", () => {
  it("pulses and announces progress while generating", () => {
    render(<StatusDot state="generating" progress={75} />);

    expect(screen.getByRole("status", { name: /generation status/i })).toHaveTextContent(
      /generating 75%/i
    );
    expect(screen.getByLabelText(/status tone/i)).toHaveStyle({ backgroundColor: "var(--accent)" });
    expect(screen.getByLabelText(/status tone/i)).toHaveAttribute("data-pulsing", "true");
  });

  it("uses the success tone when complete", () => {
    render(<StatusDot state="done" />);

    expect(screen.getByRole("status", { name: /generation status/i })).toHaveTextContent(
      /complete/i
    );
    expect(screen.getByLabelText(/status tone/i)).toHaveStyle({ backgroundColor: "var(--success)" });
  });
});
