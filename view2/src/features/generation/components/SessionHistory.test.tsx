// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import SessionHistory from "./SessionHistory";
import { useGenerationStore } from "../stores/generationStore";

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

describe("SessionHistory", () => {
  beforeEach(resetStore);

  it("shows an empty state before any completed generations", () => {
    render(<SessionHistory />);

    expect(screen.getByText(/no completed sessions yet/i)).toBeInTheDocument();
  });

  it("renders newest-first thumbnails for completed generations", () => {
    const newestPrompt =
      "Newest prompt with enough detail to exceed the eighty character visible limit in the gallery card";
    const truncatedNewestPrompt = `${newestPrompt.slice(0, 80)}…`;

    useGenerationStore.setState({
      sessionHistory: [
        {
          id: "job-new",
          imagePath: "/api/images/job-new",
          prompt: newestPrompt,
          parameters: { workflow_name: "flux2_txt2img" },
          completedAt: "2026-06-20T00:02:00Z",
        },
        {
          id: "job-old",
          imagePath: "/api/images/job-old",
          prompt: "Older prompt",
          parameters: { workflow_name: "flux2_editing" },
          completedAt: "2026-06-20T00:01:00Z",
        },
      ],
    });

    render(<SessionHistory />);

    expect(screen.getAllByRole("img")[0]).toHaveAttribute("src", "/api/images/job-new");
    expect(screen.getByText(truncatedNewestPrompt)).toHaveAttribute("title", newestPrompt);
    expect(screen.getByText("2026-06-20T00:02:00Z")).toHaveAttribute(
      "datetime",
      "2026-06-20T00:02:00Z"
    );
    expect(screen.getByText(/older prompt/i)).toBeInTheDocument();
  });
});
