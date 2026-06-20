// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useGenerationStore } from "../stores/generationStore";
import SpeedSelector from "./SpeedSelector";
import WorkflowSelector from "./WorkflowSelector";

function resetStore() {
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
}

describe("WorkflowSelector and SpeedSelector", () => {
  beforeEach(() => {
    resetStore();
  });

  it("shows the default workflow and speed choices", () => {
    render(
      <div>
        <WorkflowSelector />
        <SpeedSelector />
      </div>
    );

    expect(screen.getByRole("button", { name: /workflow: flux2_txt2img/i })).toHaveAttribute(
      "aria-haspopup",
      "listbox"
    );
    expect(screen.getByRole("button", { name: /speed: turbo/i })).toHaveAttribute(
      "aria-haspopup",
      "listbox"
    );

    fireEvent.click(screen.getByRole("button", { name: /workflow: flux2_txt2img/i }));
    expect(screen.getByRole("option", { name: "flux2_editing" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "identidad_gguf" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /speed: turbo/i }));
    expect(screen.getByRole("option", { name: /balanced/i })).toBeInTheDocument();
  });

  it("binds selections back to the generation store", () => {
    render(
      <div>
        <WorkflowSelector />
        <SpeedSelector />
      </div>
    );

    fireEvent.click(screen.getByRole("button", { name: /workflow: flux2_txt2img/i }));
    fireEvent.click(screen.getByRole("option", { name: "flux2_editing" }));

    fireEvent.click(screen.getByRole("button", { name: /speed: turbo/i }));
    fireEvent.click(screen.getByRole("option", { name: /balanced/i }));

    expect(useGenerationStore.getState().parameters.workflow_name).toBe("flux2_editing");
    expect(useGenerationStore.getState().parameters.use_turbo).toBe(false);
  });
});
