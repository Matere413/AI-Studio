import { useCallback } from "react";
import {
  DEFAULT_WS_MAX_RETRIES,
  DEFAULT_WS_RETRY_DELAY,
  connectWebSocket,
  getWsUrl,
  submitGenerate,
} from "../api/client";
import type { GenerationParameters } from "../api/types";
import { useGenerationStore } from "../stores/generationStore";

const CONNECTION_LOST_MESSAGE = "Connection lost — please try again";

export interface GenerationFlowViewModel {
  prompt: string;
  parameters: ReturnType<typeof useGenerationStore.getState>["parameters"];
  generationState: ReturnType<typeof useGenerationStore.getState>["generationState"];
  currentJob: ReturnType<typeof useGenerationStore.getState>["currentJob"];
  sessionHistory: ReturnType<typeof useGenerationStore.getState>["sessionHistory"];
  referenceFaceUrl: string | null;
  referenceGallery: string[];
  validationErrors: ReturnType<typeof useGenerationStore.getState>["validationErrors"];
  errorMessage: string | null;
  isRunning: boolean;
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  setReferenceFaceUrl(url: string | null): void;
  addToGallery(url: string): void;
  clearReferenceFace(): void;
  generate(): Promise<void>;
  cancel(): void;
  reset(): void;
}

function hasBlockingValidationErrors(
  prompt: string,
  parameters: GenerationFlowViewModel["parameters"],
  validationErrors: GenerationFlowViewModel["validationErrors"]
) {
  return (
    prompt.trim().length === 0 ||
    !parameters.workflow_name ||
    Boolean(validationErrors.prompt) ||
    Boolean(validationErrors.parameters) ||
    Boolean(validationErrors.referenceImage)
  );
}

function buildSubmissionParameters(
  parameters: GenerationFlowViewModel["parameters"],
  referenceFaceUrl: string | null
): GenerationParameters {
  if (!parameters.workflow_name) {
    throw new Error("Workflow is required");
  }

  if (parameters.workflow_name === "flux2_editing") {
    return {
      ...parameters,
      image_base64: referenceFaceUrl ?? parameters.image_base64,
      workflow_name: parameters.workflow_name,
    };
  }

  if (parameters.workflow_name === "identidad_gguf") {
    return {
      ...parameters,
      image_url: referenceFaceUrl ?? parameters.image_url,
      workflow_name: parameters.workflow_name,
    };
  }

  return {
    workflow_name: parameters.workflow_name,
    use_turbo: parameters.use_turbo,
  };
}

export function useGenerationFlow(): GenerationFlowViewModel {
  const store = useGenerationStore();

  const generate = useCallback(async () => {
    const state = useGenerationStore.getState();

    if (
      hasBlockingValidationErrors(
        state.prompt,
        state.parameters,
        state.validationErrors
      )
    ) {
      return;
    }

    try {
      const payload = buildSubmissionParameters(
        state.parameters,
        state.referenceFaceUrl
      );
      const response = await submitGenerate(state.prompt, payload);

      state.startConnecting(response.job_id);

      const cleanup = connectWebSocket(getWsUrl(response.job_id), {
        onEvent: useGenerationStore.getState().addEvent,
        onExhausted: () => useGenerationStore.getState().fail(CONNECTION_LOST_MESSAGE),
        maxRetries: DEFAULT_WS_MAX_RETRIES,
        retryDelay: DEFAULT_WS_RETRY_DELAY,
      });

      useGenerationStore.setState({ _wsCleanup: cleanup });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      useGenerationStore.getState().fail(message);
    }
  }, []);

  return {
    prompt: store.prompt,
    parameters: store.parameters,
    generationState: store.generationState,
    currentJob: store.currentJob,
    sessionHistory: store.sessionHistory,
    referenceFaceUrl: store.referenceFaceUrl,
    referenceGallery: store.referenceGallery,
    validationErrors: store.validationErrors,
    errorMessage: store.errorMessage,
    isRunning:
      store.generationState === "booting" ||
      store.generationState === "downloadingWeights" ||
      store.generationState === "generating",
    setPrompt: store.setPrompt,
    setParameters: store.setParameters,
    setReferenceFaceUrl: store.setReferenceFaceUrl,
    addToGallery: store.addToGallery,
    clearReferenceFace: store.clearReferenceFace,
    generate,
    cancel: store.cancel,
    reset: store.reset,
  };
}
