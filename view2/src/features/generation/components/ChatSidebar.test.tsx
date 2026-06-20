// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useGenerationStore } from "../stores/generationStore";
import ChatSidebar from "./ChatSidebar";

describe("ChatSidebar", () => {
  beforeEach(() => {
    useGenerationStore.setState({
      prompt: "",
      parameters: { workflow_name: "flux2_txt2img", use_turbo: true },
      currentJob: null,
      terminalEvent: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
      referenceGallery: [],
      errorMessage: null,
      validationErrors: {},
      _wsCleanup: null,
    });
  });

  it("shows the agent header and prompt composer", () => {
    render(<ChatSidebar />);

    expect(screen.getByRole("complementary", { name: /agent chat/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /agent avatar/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /agent chat/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /prompt/i })).toBeInTheDocument();
  });

  it("renders stored history entries above the composer", () => {
    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-1",
          imagePath: "/api/images/job-1",
          prompt: "A cinematic studio portrait",
          parameters: { workflow_name: "flux2_txt2img" },
          completedAt: "2026-06-19T12:34:56.000Z",
        },
      ],
    });

    render(<ChatSidebar />);

    expect(screen.getByText(/a cinematic studio portrait/i)).toBeInTheDocument();
    expect(screen.getByText(/2026/i)).toBeInTheDocument();
  });
});
