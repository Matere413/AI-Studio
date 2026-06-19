import { create } from "zustand";
import { getImageUrl } from "../api/client";
import type {
  CurrentJob,
  GenerationParameters,
  GenerationState,
  HistoryItem,
  JobEvent,
  ValidationErrors,
  WorkflowName,
} from "../api/types";
import { WORKFLOW_NAMES } from "../api/types";

export type {
  CurrentJob,
  GenerationParameters,
  GenerationState,
  HistoryItem,
  JobEvent,
  WorkflowName,
} from "../api/types";

interface GenerationStoreState {
  prompt: string;
  parameters: GenerationParameters;
  currentJob: CurrentJob | null;
  generationState: GenerationState;
  sessionHistory: HistoryItem[];
  referenceFaceUrl: string | null;
  referenceGallery: string[];
  errorMessage: string | null;
  validationErrors: ValidationErrors;
  _wsCleanup: (() => void) | null;
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  setReferenceFaceUrl(url: string): void;
  addToGallery(url: string): void;
  clearReferenceFace(): void;
  startJob(jobId: string): void;
  startConnecting(jobId: string): void;
  addEvent(event: JobEvent): void;
  setWebSocketCleanup(cleanup: (() => void) | null): void;
  fail(message: string): void;
  cancel(): void;
  reset(): void;
}

const VALID_WORKFLOWS = new Set<WorkflowName>(WORKFLOW_NAMES);

function isValidWorkflow(value: unknown): value is WorkflowName {
  return typeof value === "string" && VALID_WORKFLOWS.has(value as WorkflowName);
}

function normalizeParameters(params: GenerationParameters): GenerationParameters {
  if (params.workflow_name === "flux2_txt2img") {
    return {
      workflow_name: "flux2_txt2img",
      use_turbo: params.use_turbo ?? true,
    };
  }

  if (params.workflow_name === "flux2_editing") {
    return {
      workflow_name: "flux2_editing",
      use_turbo: params.use_turbo ?? true,
      ...(params.image_base64 ? { image_base64: params.image_base64 } : {}),
    };
  }

  if (params.workflow_name === "identidad_gguf") {
    return {
      workflow_name: "identidad_gguf",
      ...(params.image_url ? { image_url: params.image_url } : {}),
      ...(params.width !== undefined ? { width: params.width } : {}),
      ...(params.height !== undefined ? { height: params.height } : {}),
      ...(params.seed !== undefined ? { seed: params.seed } : {}),
    };
  }

  return { ...params };
}

function validatePrompt(prompt: string): string | undefined {
  if (prompt.trim().length === 0) return "Prompt is required";
  if (prompt.length > 1000) return "Prompt must be 1000 characters or less";
  return undefined;
}

function validateParameters(params: GenerationParameters): string | undefined {
  if (!params.workflow_name) return "Please select a workflow";
  if (!isValidWorkflow(params.workflow_name)) return "Invalid workflow";
  return undefined;
}

function validateReferenceImage(
  params: GenerationParameters,
  referenceFaceUrl: string | null
): string | undefined {
  if (
    (params.workflow_name === "flux2_editing" ||
      params.workflow_name === "identidad_gguf") &&
    !referenceFaceUrl
  ) {
    return "Reference image is required";
  }
  return undefined;
}

function stateFromEvent(event: JobEvent): GenerationState {
  if (event.event === "booting_server") return "booting";
  if (event.event === "downloading_weights") return "downloadingWeights";
  if (event.event === "generating" || event.event === "progress") return "generating";
  if (event.event === "completed") return "done";
  if (event.event === "error") return "error";
  return "idle";
}

const initialState = {
  prompt: "",
  parameters: { workflow_name: "flux2_txt2img" as WorkflowName },
  currentJob: null,
  generationState: "idle" as GenerationState,
  sessionHistory: [],
  referenceFaceUrl: null,
  referenceGallery: [],
  errorMessage: null,
  validationErrors: {},
  _wsCleanup: null,
};

export const useGenerationStore = create<GenerationStoreState>((set, get) => ({
  ...initialState,

  setPrompt: (value) => {
    set({
      prompt: value,
      validationErrors: {
        ...get().validationErrors,
        prompt: validatePrompt(value),
      },
    });
  },

  setParameters: (value) => {
    const parameters = normalizeParameters({ ...get().parameters, ...value });
    set({
      parameters,
      validationErrors: {
        ...get().validationErrors,
        parameters: validateParameters(parameters),
        referenceImage: validateReferenceImage(parameters, get().referenceFaceUrl),
      },
    });
  },

  setReferenceFaceUrl: (url) => {
    set({
      referenceFaceUrl: url,
      validationErrors: {
        ...get().validationErrors,
        referenceImage: validateReferenceImage(get().parameters, url),
      },
    });
  },

  addToGallery: (url) => {
    if (get().referenceGallery.includes(url)) return;
    set({ referenceGallery: [url, ...get().referenceGallery] });
  },

  clearReferenceFace: () => {
    const parameters = { ...get().parameters };
    delete parameters.image_base64;
    delete parameters.image_url;
    set({
      referenceFaceUrl: null,
      parameters,
      validationErrors: {
        ...get().validationErrors,
        referenceImage: validateReferenceImage(parameters, null),
      },
    });
  },

  startJob: (jobId) => {
    set({
      generationState: "booting",
      currentJob: {
        job_id: jobId,
        status: "connecting",
        progress: null,
        events: [],
      },
      errorMessage: null,
    });
  },

  startConnecting: (jobId) => get().startJob(jobId),

  addEvent: (event) => {
    const state = get();
    if (!state.currentJob) return;

    const currentJob: CurrentJob = {
      ...state.currentJob,
      status: event.event,
      progress: event.progress ?? state.currentJob.progress,
      events: [...state.currentJob.events, event],
    };

    if (event.event === "completed") {
      const historyItem: HistoryItem = {
        id: event.job_id,
        imagePath: getImageUrl(event.job_id),
        prompt: state.prompt,
        parameters: state.parameters,
        completedAt: event.timestamp,
      };
      set({
        generationState: "done",
        currentJob: null,
        sessionHistory: [historyItem, ...state.sessionHistory],
        errorMessage: null,
      });
      return;
    }

    if (event.event === "error") {
      set({
        generationState: "error",
        currentJob: null,
        errorMessage: event.error?.detail ?? event.message ?? "Generation failed",
      });
      return;
    }

    set({
      generationState: stateFromEvent(event),
      currentJob,
    });
  },

  setWebSocketCleanup: (cleanup) => set({ _wsCleanup: cleanup }),

  fail: (message) => {
    set({
      generationState: "error",
      currentJob: null,
      errorMessage: message,
    });
  },

  cancel: () => {
    get()._wsCleanup?.();
    set({
      generationState: "idle",
      currentJob: null,
      errorMessage: null,
      _wsCleanup: null,
    });
  },

  reset: () => {
    get()._wsCleanup?.();
    set({ ...initialState });
  },
}));
