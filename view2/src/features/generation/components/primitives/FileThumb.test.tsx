import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FileThumb } from "./FileThumb";

describe("FileThumb", () => {
  it("renders the asset thumbnail, name, and remove control", () => {
    render(
      <FileThumb
        asset={{ id: "asset-1", name: "reference.png", url: "/reference.png" }}
        onRemove={() => {}}
      />
    );

    expect(screen.getByText("reference.png")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove reference\.png/i })).toBeInTheDocument();
  });

  it("calls onRemove when the remove control is activated", () => {
    const onRemove = vi.fn();

    render(
      <FileThumb
        asset={{ id: "asset-1", name: "reference.png", url: "/reference.png" }}
        onRemove={onRemove}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /remove reference\.png/i }));

    expect(onRemove).toHaveBeenCalledWith("asset-1");
  });
});
