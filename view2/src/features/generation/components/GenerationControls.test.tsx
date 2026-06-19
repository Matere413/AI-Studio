import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useUiStore } from "../stores/uiStore";
import { GenerationControls } from "./GenerationControls";

describe("GenerationControls", () => {
  beforeEach(() => {
    useUiStore.getState().setAspectRatio("1:1");
  });

  it("toggles speed and updates the aspect ratio store", () => {
    const onUseTurboChange = vi.fn();

    render(
      <GenerationControls
        onUseTurboChange={onUseTurboChange}
        useTurbo={true}
        workflow="flux2_txt2img"
      />,
    );

    expect(screen.getByRole("button", { name: /fast/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /quality/i })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: /quality/i }));
    fireEvent.change(screen.getByLabelText(/aspect ratio/i), { target: { value: "16:9" } });

    expect(onUseTurboChange).toHaveBeenCalledWith(false);
    expect(useUiStore.getState().aspectRatio).toBe("16:9");
  });

  it("can switch back to fast rendering and portrait framing", () => {
    const onUseTurboChange = vi.fn();

    render(
      <GenerationControls
        onUseTurboChange={onUseTurboChange}
        useTurbo={false}
        workflow="flux2_txt2img"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /fast/i }));
    fireEvent.change(screen.getByLabelText(/aspect ratio/i), { target: { value: "9:16" } });

    expect(onUseTurboChange).toHaveBeenCalledWith(true);
    expect(useUiStore.getState().aspectRatio).toBe("9:16");
  });

  it("disables controls when no workflow is selected", () => {
    render(<GenerationControls onUseTurboChange={() => {}} useTurbo={true} />);

    expect(screen.getByRole("button", { name: /fast/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /quality/i })).toBeDisabled();
    expect(screen.getByLabelText(/aspect ratio/i)).toBeDisabled();
  });
});
