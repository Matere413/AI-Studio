import { beforeEach, describe, expect, it } from "vitest";
import { useGenerationStore } from "./generationStore";

function resetStore() {
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
}

describe("generationStore", () => {
  beforeEach(() => {
    resetStore();
  });

  it("starts with the expected empty generation state", () => {
    const state = useGenerationStore.getState();

    expect(state.prompt).toBe("");
    expect(state.parameters).toEqual({});
    expect(state.currentJob).toBeNull();
    expect(state.generationState).toBe("idle");
    expect(state.sessionHistory).toEqual([]);
    expect(state.referenceFaceUrl).toBeNull();
    expect(state.referenceGallery).toEqual([]);
  });

  it("validates prompt and binds the selected workflow into parameters", () => {
    useGenerationStore.getState().setPrompt("   ");
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });

    expect(useGenerationStore.getState().validationErrors.prompt).toBe(
      "Prompt is required"
    );
    expect(useGenerationStore.getState().parameters).toEqual({
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });

    useGenerationStore.getState().setParameters({
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,old-value",
    });

    expect(useGenerationStore.getState().parameters).toEqual({
      workflow_name: "identidad_gguf",
      image_url: "data:image/png;base64,old-value",
    });
  });

  it("removes reference assets from the gallery", () => {
    useGenerationStore.getState().setReferenceFaceUrl("data:image/png;base64,alpha");
    useGenerationStore.getState().addToGallery("data:image/png;base64,alpha");

    useGenerationStore.getState().removeFromGallery("data:image/png;base64,alpha");

    expect(useGenerationStore.getState().referenceGallery).toEqual([]);
    expect(useGenerationStore.getState().referenceFaceUrl).toBeNull();
    expect(useGenerationStore.getState().parameters).not.toHaveProperty("image_url");
    expect(useGenerationStore.getState().parameters).not.toHaveProperty("image_base64");
  });

  it("maps backend events to generation states and session history", () => {
    useGenerationStore.getState().setPrompt("A cinematic portrait");
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    useGenerationStore.getState().startConnecting("job-123");

    useGenerationStore.getState().addEvent({
      event: "booting_server",
      job_id: "job-123",
      timestamp: "2026-06-19T12:00:00.000Z",
    });

    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "booting",
        currentJob: expect.objectContaining({
          job_id: "job-123",
          status: "booting_server",
          progress: null,
        }),
      })
    );

    useGenerationStore.getState().addEvent({
      event: "progress",
      job_id: "job-123",
      timestamp: "2026-06-19T12:00:01.000Z",
      progress: 64,
    });

    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "generating",
        currentJob: expect.objectContaining({ progress: 64, status: "progress" }),
      })
    );

    useGenerationStore.getState().addEvent({
      event: "completed",
      job_id: "job-123",
      timestamp: "2026-06-19T12:00:02.000Z",
      result: { image_path: "backend/result.png" },
    });

    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "done",
        currentJob: null,
        terminalEvent: expect.objectContaining({
          event: "completed",
          job_id: "job-123",
        }),
        sessionHistory: [
          expect.objectContaining({
            id: "job-123",
            imagePath: "/api/images/job-123",
            prompt: "A cinematic portrait",
          }),
        ],
      })
    );

    useGenerationStore.getState().startConnecting("job-456");
    useGenerationStore.getState().addEvent({
      event: "error",
      job_id: "job-456",
      timestamp: "2026-06-19T12:00:03.000Z",
      error: { code: "comfyui_execution_failed", detail: "Boom" },
    });

    expect(useGenerationStore.getState()).toEqual(
      expect.objectContaining({
        generationState: "error",
        currentJob: null,
        terminalEvent: expect.objectContaining({
          event: "error",
          job_id: "job-456",
        }),
        errorMessage: "Boom",
      })
    );
  });
});
