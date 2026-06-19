import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkspaceCanvas } from "./WorkspaceCanvas";

describe("WorkspaceCanvas", () => {
  it("renders a dotted canvas surface and studio workspace placeholder", () => {
    render(<WorkspaceCanvas state="idle" />);

    expect(screen.getByRole("main", { name: /studio workspace/i })).toBeInTheDocument();
    expect(screen.getByText("No output yet")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Awaiting generation");
    expect(document.querySelector(".surface-canvas")).toBeInTheDocument();
  });

  it("renders generation progress with a caption and thin progress indicator", () => {
    render(<WorkspaceCanvas state="generating" progress={42} />);

    expect(screen.getByRole("status")).toHaveTextContent(/generating/i);
    expect(screen.getByText(/42%/i)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "42");
  });

  it("renders cold-start labels with indeterminate progress before numeric progress", () => {
    const { rerender } = render(<WorkspaceCanvas state="booting" progress={null} />);

    expect(screen.getByRole("status")).toHaveTextContent("Starting server...");
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");

    rerender(<WorkspaceCanvas state="downloadingWeights" progress={null} />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading model weights...");
    expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
  });

  it("renders result images and errors in their dedicated states", () => {
    const { rerender } = render(
      <WorkspaceCanvas
        state="done"
        imageUrl="/api/images/job-1"
        prompt="Matte product hero shot"
      />
    );

    expect(screen.getByRole("img", { name: /matte product hero shot/i })).toHaveAttribute(
      "src",
      "/api/images/job-1"
    );

    rerender(<WorkspaceCanvas state="error" errorMessage="Backend failed" />);

    expect(screen.getByRole("alert")).toHaveTextContent("Backend failed");
  });
});
