import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InputBar } from "./InputBar";

describe("InputBar", () => {
  it("renders the prompt textarea, attach control, and circular send action", () => {
    render(<InputBar value="" onChange={() => {}} onSubmit={() => {}} />);

    expect(screen.getByRole("textbox", { name: /prompt/i })).toHaveClass("input");
    expect(screen.getByRole("button", { name: /attach reference/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send prompt/i })).toHaveClass(
      "btn",
      "btn-primary",
      "btn-icon-circle"
    );
  });

  it("submits non-empty prompts by button click and Enter", () => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();

    render(
      <InputBar value="Generate a matte black espresso cup" onChange={onChange} onSubmit={onSubmit} />
    );

    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));
    fireEvent.keyDown(screen.getByRole("textbox", { name: /prompt/i }), { key: "Enter" });

    expect(onSubmit).toHaveBeenCalledTimes(2);
  });

  it("disables empty prompts and exposes validation feedback", () => {
    const onSubmit = vi.fn();

    render(<InputBar value="   " onChange={() => {}} onSubmit={onSubmit} />);

    expect(screen.getByRole("button", { name: /send prompt/i })).toBeDisabled();

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Prompt is required");
  });

  it("disables submission while reference validation is active", () => {
    const onSubmit = vi.fn();

    render(
      <InputBar
        value="Generate a character portrait"
        onChange={() => {}}
        onSubmit={onSubmit}
        validationError="Reference image required"
      />,
    );

    expect(screen.getByRole("button", { name: /send prompt/i })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Reference image required");
  });
});
