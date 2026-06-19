import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentAvatar } from "./AgentAvatar";

describe("AgentAvatar", () => {
  it("renders initials when no image source is available", () => {
    render(<AgentAvatar name="Nova Studio" />);

    expect(screen.getByText("NS")).toBeInTheDocument();
  });

  it("renders the provided image when available", () => {
    render(<AgentAvatar name="Nova Studio" src="/agent.png" />);

    expect(screen.getByRole("img", { name: /nova studio/i })).toHaveAttribute(
      "src",
      "/agent.png"
    );
  });
});
