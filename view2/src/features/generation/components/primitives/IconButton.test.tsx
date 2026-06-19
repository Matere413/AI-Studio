import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Menu } from "lucide-react";
import { IconButton } from "./IconButton";

describe("IconButton", () => {
  it("renders an accessible 44px control with a visible focus class", () => {
    render(
      <IconButton label="Open navigation menu">
        <Menu aria-hidden="true" />
      </IconButton>
    );

    const button = screen.getByRole("button", { name: /open navigation menu/i });

    expect(button).toHaveAttribute("aria-label", "Open navigation menu");
    expect(button).toHaveStyle({ minHeight: "44px", minWidth: "44px" });

    fireEvent.focus(button);
    expect(button).toHaveClass("focus-visible");
  });

  it("forwards click events and supports disabled state", () => {
    const onClick = vi.fn();

    const { rerender } = render(
      <IconButton label="Open navigation menu" onClick={onClick}>
        <Menu aria-hidden="true" />
      </IconButton>
    );

    fireEvent.click(screen.getByRole("button", { name: /open navigation menu/i }));
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <IconButton disabled label="Open navigation menu" onClick={onClick}>
        <Menu aria-hidden="true" />
      </IconButton>
    );

    fireEvent.click(screen.getByRole("button", { name: /open navigation menu/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /open navigation menu/i })).toBeDisabled();
  });
});
