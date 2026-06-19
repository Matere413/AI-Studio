import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatSidebar } from "./ChatSidebar";

describe("ChatSidebar", () => {
  it("renders the agent chat panel, messages, workflow selector, and input bar", () => {
    render(
      <ChatSidebar
        prompt=""
        workflow="flux2_txt2img"
        messages={[
          { id: "1", role: "user", content: "Make a campaign image", timestamp: "14:02" },
          { id: "2", role: "agent", content: "Ready to generate.", timestamp: "14:03" },
        ]}
        onPromptChange={() => {}}
        onWorkflowChange={() => {}}
        onSubmit={() => {}}
      />
    );

    expect(screen.getByRole("complementary", { name: /agent chat/i })).toHaveClass(
      "surface-panel"
    );
    expect(screen.getByText("Make a campaign image")).toBeInTheDocument();
    expect(screen.getByLabelText(/workflow/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/prompt/i)).toBeInTheDocument();
  });

  it("forwards prompt, workflow, and submit interactions", () => {
    const onPromptChange = vi.fn();
    const onWorkflowChange = vi.fn();
    const onSubmit = vi.fn();

    render(
      <ChatSidebar
        prompt="Generate packaging mockup"
        workflow="flux2_txt2img"
        messages={[]}
        onPromptChange={onPromptChange}
        onWorkflowChange={onWorkflowChange}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: "New prompt" },
    });
    fireEvent.change(screen.getByLabelText(/workflow/i), {
      target: { value: "identidad_gguf" },
    });
    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    expect(onPromptChange).toHaveBeenCalledWith("New prompt");
    expect(onWorkflowChange).toHaveBeenCalledWith("identidad_gguf");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
