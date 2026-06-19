import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowSelector } from "./WorkflowSelector";

describe("WorkflowSelector", () => {
  it("defaults to the base txt2img workflow and uses compact technical styling", () => {
    render(<WorkflowSelector onChange={() => {}} />);

    const selector = screen.getByLabelText(/workflow/i);
    expect(selector).toHaveValue("flux2_txt2img");
    expect(selector).toHaveClass("input", "text-mono");
  });

  it("offers the three manual workflows and reports changes", () => {
    const onChange = vi.fn();
    render(<WorkflowSelector value="flux2_txt2img" onChange={onChange} />);

    expect(screen.getByRole("option", { name: /base txt2img/i })).toHaveValue(
      "flux2_txt2img"
    );
    expect(screen.getByRole("option", { name: /flux editing/i })).toHaveValue(
      "flux2_editing"
    );
    expect(screen.getByRole("option", { name: /identity gguf/i })).toHaveValue(
      "identidad_gguf"
    );

    fireEvent.change(screen.getByLabelText(/workflow/i), {
      target: { value: "flux2_editing" },
    });

    expect(onChange).toHaveBeenCalledWith("flux2_editing");
  });
});
