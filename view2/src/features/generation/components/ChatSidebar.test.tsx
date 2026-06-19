import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatSidebar } from "./ChatSidebar";

describe("ChatSidebar", () => {
  it("renders the agent chat panel, avatar, messages, input bar, and generation controls", () => {
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
    expect(screen.getByRole("img", { name: /orchestrator/i })).toBeInTheDocument();
    expect(screen.getByText("Make a campaign image")).toBeInTheDocument();
    expect(screen.getByLabelText(/workflow/i)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /prompt/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /generation controls/i })).toBeInTheDocument();

    const prompt = screen.getByRole("textbox", { name: /prompt/i });
    const controls = screen.getByRole("group", { name: /generation controls/i });
    expect(prompt.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("forwards prompt, workflow, speed, and submit interactions", () => {
    const onPromptChange = vi.fn();
    const onWorkflowChange = vi.fn();
    const onUseTurboChange = vi.fn();
    const onSubmit = vi.fn();

    render(
      <ChatSidebar
        prompt="Generate packaging mockup"
        workflow="flux2_txt2img"
        messages={[]}
        onPromptChange={onPromptChange}
        onUseTurboChange={onUseTurboChange}
        onWorkflowChange={onWorkflowChange}
        onSubmit={onSubmit}
        useTurbo={true}
      />
    );

    fireEvent.change(screen.getByRole("textbox", { name: /prompt/i }), {
      target: { value: "New prompt" },
    });
    fireEvent.change(screen.getByLabelText(/workflow/i), {
      target: { value: "identidad_gguf" },
    });
    fireEvent.click(screen.getByRole("button", { name: /quality/i }));
    fireEvent.click(screen.getByRole("button", { name: /send prompt/i }));

    expect(onPromptChange).toHaveBeenCalledWith("New prompt");
    expect(onWorkflowChange).toHaveBeenCalledWith("identidad_gguf");
    expect(onUseTurboChange).toHaveBeenCalledWith(false);
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
