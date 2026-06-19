import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusDot } from "./StatusDot";

describe("StatusDot", () => {
  it.each([
    ["amber", "status-dot--amber"],
    ["green", "status-dot--green"],
    ["red", "status-dot--red"],
  ] as const)("maps %s status to %s", (status, modifierClass) => {
    const { container } = render(<StatusDot status={status} />);

    expect(container.firstElementChild).toHaveClass("status-dot", modifierClass);
  });
});
