import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InputBar } from "./InputBar";

describe("InputBar", () => {
  it("renders the prompt textarea and primary send action with design-system classes", () => {
    render(<InputBar value="" onChange={() => {}} onSubmit={() => {}} />);

    expect(screen.getByLabelText(/prompt/i)).toHaveClass("input");
    expect(screen.getByRole("button", { name: /send prompt/i })).toHaveClass(
      "btn",
      "btn-primary"
    );
  });

  it("submits non-empty prompts by button click and Enter", () => {
    const onSubmit = vi.fn();
    const onChange = vi.fn();

    render(
      <InputBar value="Generate a matte black espresso cup" onChange={onChange} onSubmit={onSubmit} />
    );

    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));
    fireEvent.keyDown(screen.getByLabelText(/prompt/i), { key: "Enter" });

    expect(onSubmit).toHaveBeenCalledTimes(2);
  });

  it("blocks empty prompts and exposes validation feedback", () => {
    const onSubmit = vi.fn();

    render(<InputBar value="   " onChange={() => {}} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Prompt is required");
  });
});
