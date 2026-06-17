"use client";

import { useCallback } from "react";
import { connectWebSocket, getWsUrl, submitGenerate } from "../api/client";
import { useGenerationStore, type JobEvent } from "../stores/generationStore";

export function useGenerationFlow() {
  const prompt = useGenerationStore((s) => s.prompt);
  const parameters = useGenerationStore((s) => s.parameters);
  const referenceFaceUrl = useGenerationStore((s) => s.referenceFaceUrl);
  const referenceGallery = useGenerationStore((s) => s.referenceGallery);
  const generationState = useGenerationStore((s) => s.generationState);
  const validationErrors = useGenerationStore((s) => s.validationErrors);
  const setPrompt = useGenerationStore((s) => s.setPrompt);
  const setParameters = useGenerationStore((s) => s.setParameters);
  const setReferenceFaceUrl = useGenerationStore((s) => s.setReferenceFaceUrl);
  const addToGallery = useGenerationStore((s) => s.addToGallery);
  const clearReferenceFace = useGenerationStore((s) => s.clearReferenceFace);
  const startConnecting = useGenerationStore((s) => s.startConnecting);
  const addEvent = useGenerationStore((s) => s.addEvent);
  const fail = useGenerationStore((s) => s.fail);
  const cancel = useGenerationStore((s) => s.cancel);
  const reset = useGenerationStore((s) => s.reset);

  const isRunning =
    generationState === "connecting" || generationState === "generating";
  const hasErrors = Boolean(
    validationErrors.prompt ||
      validationErrors.parameters ||
      validationErrors.referenceImage
  );

  const generate = useCallback(async () => {
    if (!prompt.trim() || hasErrors) return;

    try {
      const submissionParameters =
        (parameters.workflow_name === "identidad_gguf" || parameters.workflow_name === "flux2_editing") &&
        referenceFaceUrl
          ? { ...parameters, ...(parameters.workflow_name === "identidad_gguf" ? { image_url: referenceFaceUrl } : {}), ...(parameters.workflow_name === "flux2_editing" ? { image_base64: referenceFaceUrl } : {}) }
          : parameters;
      const response = await submitGenerate(prompt, submissionParameters);
      startConnecting(response.job_id);

      const wsUrl = getWsUrl(response.job_id);
      const cleanup = connectWebSocket(wsUrl, {
        onEvent: (event) => addEvent(event as JobEvent),
        onExhausted: () => fail("Connection lost — please try again"),
        maxRetries: 3,
      });

      useGenerationStore.setState({ _wsCleanup: cleanup });
    } catch (err) {
      fail(err instanceof Error ? err.message : "Generation failed");
    }
  }, [prompt, parameters, referenceFaceUrl, hasErrors, startConnecting, addEvent, fail]);

  return {
    prompt,
    parameters,
    referenceFaceUrl,
    referenceGallery,
    generationState,
    validationErrors,
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
