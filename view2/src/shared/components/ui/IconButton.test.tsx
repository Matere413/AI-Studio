// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import styles from "@/features/generation/components/GenerationStudio.module.css";
import IconButton from "./IconButton";

describe("IconButton", () => {
  it("keeps the shared button class when callers pass className", () => {
    render(
      <IconButton aria-label="Demo action" className="extra-class">
        +
      </IconButton>
    );

    const button = screen.getByRole("button", { name: "Demo action" });

    expect(button).toHaveClass(styles.iconButton);
    expect(button).toHaveClass("extra-class");
  });
});
