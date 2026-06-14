import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PixelProgressBar from "./PixelProgressBar";

describe("PixelProgressBar (Spec: Cold Start — Scenarios: Cold start delay, Becomes determinate)", () => {
  it("renders no percentage text when isColdStart is true (Spec: Cold Start — Scenario: Cold start delay)", () => {
    const { container } = render(
      <PixelProgressBar progress={null} isColdStart={true} />
    );
    // Indeterminate bar has no percentage label
    expect(container.textContent).not.toMatch(/\d+%/);
  });

  it("renders no percentage text when progress is null regardless of isColdStart", () => {
    const { container } = render(
      <PixelProgressBar progress={null} isColdStart={false} />
    );
    // Indeterminate bar has no percentage label
    expect(container.textContent).not.toMatch(/\d+%/);
  });

  it("shows determinate bar with percentage when progress is provided (Spec: Cold Start — Scenario: Becomes determinate)", () => {
    render(<PixelProgressBar progress={0.42} isColdStart={false} />);
    expect(screen.getByText("42%")).toBeInTheDocument();
  });

  it("shows 0% when progress is 0 and not cold start", () => {
    render(<PixelProgressBar progress={0} isColdStart={false} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("shows 100% when progress is 1", () => {
    render(<PixelProgressBar progress={1} isColdStart={false} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("clamps progress above 1 to 100%", () => {
    render(<PixelProgressBar progress={1.5} isColdStart={false} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("clamps progress below 0 to 0%", () => {
    render(<PixelProgressBar progress={-0.5} isColdStart={false} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});