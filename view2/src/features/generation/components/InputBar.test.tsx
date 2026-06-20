// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGenerationStore } from "../stores/generationStore";
import InputBar from "./InputBar";

const generate = vi.fn();

vi.mock("../hooks/useGenerationFlow", () => ({
  useGenerationFlow: () => ({
    generate,
    generationState: "idle",
    validationErrors: {},
    isRunning: false,
  }),
}));

describe("InputBar", () => {
  beforeEach(() => {
    generate.mockReset();
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

  it("submits the prompt when Enter is pressed", () => {
    useGenerationStore.setState({ prompt: "A cinematic portrait" });

    render(<InputBar />);

    fireEvent.keyDown(screen.getByRole("textbox", { name: /prompt/i }), {
      key: "Enter",
      code: "Enter",
    });

    expect(generate).toHaveBeenCalledTimes(1);
  });

  it("disables submit when the prompt is empty", () => {
    render(<InputBar />);

    expect(screen.getByRole("button", { name: /send prompt/i })).toBeDisabled();
    fireEvent.keyDown(screen.getByRole("textbox", { name: /prompt/i }), {
      key: "Enter",
      code: "Enter",
    });
    expect(generate).not.toHaveBeenCalled();
  });
});
