// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import OutputCanvas from "./OutputCanvas";
import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

const resetStore = () =>
  useGenerationStore.setState({
    prompt: "",
    parameters: {},
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

describe("OutputCanvas", () => {
  beforeEach(resetStore);

  it("shows dotted artboard chrome when idle", () => {
    render(<OutputCanvas />);

    expect(screen.getByRole("region", { name: /output canvas/i })).toHaveAttribute(
      "data-surface",
      "dotted"
    );
    expect(screen.getByRole("region", { name: /output canvas/i })).toHaveClass(styles.outputCanvas);
    expect(screen.getByRole("article", { name: /artboard chrome/i })).toHaveClass(styles.outputArtboard);
    expect(screen.getByText(/prompt caption/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/canvas bottom rail/i)).toBeInTheDocument();
  });

  it("renders the latest completed image", () => {
    useGenerationStore.setState({
      prompt: "A sunset over dunes",
      generationState: "done",
      sessionHistory: [
        {
          id: "job-1",
          imagePath: "/api/images/job-1",
          prompt: "A sunset over dunes",
          parameters: { workflow_name: "flux2_txt2img" },
          completedAt: "2026-06-20T00:00:00Z",
        },
      ],
    });

    render(<OutputCanvas />);

    expect(screen.getByRole("status", { name: /generation status/i })).toHaveTextContent(
      /complete/i
    );
    expect(screen.getByRole("img", { name: /generated image for a sunset over dunes/i })).toHaveAttribute(
      "src",
      "/api/images/job-1"
    );
  });
});
