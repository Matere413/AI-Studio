import { beforeEach, describe, expect, it, vi } from "vitest";
import { useGenerationStore, type WorkflowName } from "./generationStore";

describe("generationStore", () => {
  beforeEach(() => {
    useGenerationStore.getState().reset();
  });

  it("starts with prompt, params, job, validation, and reference assets reset", () => {
    expect(useGenerationStore.getState()).toMatchObject({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
      referenceGallery: [],
      validationErrors: {},
    });
  });

  it("validates prompt and workflow inputs", () => {
    useGenerationStore.getState().setPrompt("   ");
    useGenerationStore
      .getState()
      .setParameters({ workflow_name: "legacy" as WorkflowName });

    expect(useGenerationStore.getState().validationErrors).toMatchObject({
      prompt: "Prompt is required",
      parameters: "Invalid workflow",
    });

    useGenerationStore.getState().setPrompt("A premium studio portrait");
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });

    expect(useGenerationStore.getState().validationErrors.prompt).toBeUndefined();
    expect(useGenerationStore.getState().validationErrors.parameters).toBeUndefined();
  });

  it("normalizes workflow-scoped parameters and reference requirements", () => {
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    expect(useGenerationStore.getState().parameters).toEqual({
      workflow_name: "flux2_txt2img",
      use_turbo: true,
    });

    useGenerationStore.getState().setParameters({ workflow_name: "identidad_gguf" });
    expect(useGenerationStore.getState().parameters).toEqual({
      workflow_name: "identidad_gguf",
    });
    expect(useGenerationStore.getState().validationErrors.referenceImage).toBe(
      "Reference image is required"
    );

    useGenerationStore
      .getState()
      .setReferenceFaceUrl("data:image/png;base64,aWQ=");
    expect(
      useGenerationStore.getState().validationErrors.referenceImage
    ).toBeUndefined();
  });

  it("tracks a unique reference gallery and clears selected references", () => {
    useGenerationStore.getState().addToGallery("data:image/png;base64,MQ==");
    useGenerationStore.getState().addToGallery("data:image/png;base64,Mg==");
    useGenerationStore.getState().addToGallery("data:image/png;base64,MQ==");
    useGenerationStore
      .getState()
      .setReferenceFaceUrl("data:image/png;base64,MQ==");

    expect(useGenerationStore.getState().referenceGallery).toEqual([
      "data:image/png;base64,Mg==",
      "data:image/png;base64,MQ==",
    ]);

    useGenerationStore.getState().clearReferenceFace();
    expect(useGenerationStore.getState().referenceFaceUrl).toBeNull();
  });

  it("maps backend event names into the frontend state machine", () => {
    useGenerationStore.getState().startJob("job-1");
    expect(useGenerationStore.getState().generationState).toBe("booting");

    useGenerationStore.getState().addEvent({
      event: "downloading_weights",
      job_id: "job-1",
      timestamp: "2026-06-18T00:00:00.000Z",
    });
    expect(useGenerationStore.getState().generationState).toBe(
      "downloadingWeights"
    );

    useGenerationStore.getState().addEvent({
      event: "progress",
      job_id: "job-1",
      timestamp: "2026-06-18T00:00:01.000Z",
      progress: 42,
    });
    expect(useGenerationStore.getState().generationState).toBe("generating");
    expect(useGenerationStore.getState().currentJob?.progress).toBe(42);
  });

  it("creates history from completed events using the image proxy URL", () => {
    useGenerationStore.getState().setPrompt("Output prompt");
    useGenerationStore.getState().setParameters({ workflow_name: "flux2_txt2img" });
    useGenerationStore.getState().startJob("job-done");

    useGenerationStore.getState().addEvent({
      event: "completed",
      job_id: "job-done",
      timestamp: "2026-06-18T00:01:00.000Z",
    });

    expect(useGenerationStore.getState()).toMatchObject({
      generationState: "done",
      currentJob: null,
    });
    expect(useGenerationStore.getState().sessionHistory[0]).toMatchObject({
      id: "job-done",
      imagePath: "/api/images/job-done",
      prompt: "Output prompt",
    });
  });

  it("fails, cancels, and resets in-flight cleanup", () => {
    const cleanup = vi.fn();
    useGenerationStore.getState().startJob("job-2");
    useGenerationStore.getState().setWebSocketCleanup(cleanup);

    useGenerationStore.getState().cancel();
    expect(cleanup).toHaveBeenCalledTimes(1);
    expect(useGenerationStore.getState().generationState).toBe("idle");

    useGenerationStore.getState().fail("Connection lost");
    expect(useGenerationStore.getState()).toMatchObject({
      generationState: "error",
      errorMessage: "Connection lost",
      currentJob: null,
    });
  });
});
