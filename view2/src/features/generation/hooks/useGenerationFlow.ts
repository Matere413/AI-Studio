"use client";

import { useCallback } from "react";
import { connectWebSocket, getWsUrl, submitGenerate } from "../api/client";
import { useGenerationStore, type JobEvent } from "../stores/generationStore";

export function useGenerationFlow() {
  const prompt = useGenerationStore((state) => state.prompt);
  const parameters = useGenerationStore((state) => state.parameters);
  const referenceFaceUrl = useGenerationStore((state) => state.referenceFaceUrl);
  const referenceGallery = useGenerationStore((state) => state.referenceGallery);
  const currentJob = useGenerationStore((state) => state.currentJob);
  const generationState = useGenerationStore((state) => state.generationState);
  const validationErrors = useGenerationStore((state) => state.validationErrors);
  const errorMessage = useGenerationStore((state) => state.errorMessage);
  const sessionHistory = useGenerationStore((state) => state.sessionHistory);
  const setPrompt = useGenerationStore((state) => state.setPrompt);
  const setParameters = useGenerationStore((state) => state.setParameters);
  const setReferenceFaceUrl = useGenerationStore(
    (state) => state.setReferenceFaceUrl
  );
  const addToGallery = useGenerationStore((state) => state.addToGallery);
  const clearReferenceFace = useGenerationStore(
    (state) => state.clearReferenceFace
  );
  const startJob = useGenerationStore((state) => state.startJob);
  const addEvent = useGenerationStore((state) => state.addEvent);
  const setWebSocketCleanup = useGenerationStore(
    (state) => state.setWebSocketCleanup
  );
  const fail = useGenerationStore((state) => state.fail);
  const cancel = useGenerationStore((state) => state.cancel);
  const reset = useGenerationStore((state) => state.reset);

  const hasErrors = Boolean(
    validationErrors.prompt ||
      validationErrors.parameters ||
      validationErrors.referenceImage
  );
  const isRunning =
    generationState === "booting" ||
    generationState === "downloadingWeights" ||
    generationState === "generating";

  const generate = useCallback(async () => {
    // Read latest state directly to avoid stale closures in event handlers
    const latest = useGenerationStore.getState();
    const trimmedPrompt = latest.prompt.trim();
    const latestErrors = latest.validationErrors;
    const latestHasErrors = Boolean(
      latestErrors.prompt || latestErrors.parameters || latestErrors.referenceImage,
    );

    if (!trimmedPrompt || latestHasErrors) return;

    const submissionParameters = { ...latest.parameters };
    if (latest.parameters.workflow_name === "identidad_gguf" && latest.referenceFaceUrl) {
      submissionParameters.image_url = latest.referenceFaceUrl;
    }
    if (latest.parameters.workflow_name === "flux2_editing" && latest.referenceFaceUrl) {
      submissionParameters.image_base64 = latest.referenceFaceUrl;
    }

    try {
      const response = await submitGenerate(trimmedPrompt, submissionParameters);
      startJob(response.job_id);

      const cleanup = connectWebSocket(getWsUrl(response.job_id), {
        onEvent: (event) => addEvent(event as JobEvent),
        onExhausted: () => fail("Connection lost — please try again"),
        maxRetries: 3,
      });
      setWebSocketCleanup(cleanup);
    } catch (error) {
      fail(error instanceof Error ? error.message : "Generation failed");
    }
  }, [addEvent, fail, setWebSocketCleanup, startJob]);

  return {
    prompt,
    parameters,
    referenceFaceUrl,
    referenceGallery,
    currentJob,
    generationState,
    validationErrors,
    errorMessage,
    sessionHistory,
    isRunning,
    hasErrors,
    setPrompt,
    setParameters,
    setReferenceFaceUrl,
    addToGallery,
    clearReferenceFace,
    generate,
    cancel,
    reset,
  };
}

export type GenerationFlowViewModel = ReturnType<typeof useGenerationFlow>;
