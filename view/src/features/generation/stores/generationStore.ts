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

export type {
  CurrentJob,
  GenerationParameters,
  GenerationState,
  HistoryItem,
  JobEvent,
  WorkflowName,
} from "../api/types";

interface GenerationStore {
  prompt: string;
  parameters: GenerationParameters;
  currentJob: CurrentJob | null;
  generationState: GenerationState;
  sessionHistory: HistoryItem[];
  referenceFaceUrl: string | null;
  referenceGallery: string[];
  errorMessage: string | null;
  validationErrors: ValidationErrors;
  /** Internal: WebSocket cleanup function (not reactive) */
  _wsCleanup: (() => void) | null;
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  setReferenceFaceUrl(url: string): void;
  addToGallery(url: string): void;
  clearReferenceFace(): void;
  startConnecting(jobId: string): void;
  addEvent(event: JobEvent): void;
  fail(message: string): void;
  cancel(): void;
  reset(): void;
}

const VALID_WORKFLOWS: WorkflowName[] = [
  "flux2_txt2img",
  "flux2_editing",
  "identidad_gguf",
];

function normalizeParameters(params: GenerationParameters): GenerationParameters {
  const workflow = params.workflow_name;

  if (workflow === "flux2_txt2img") {
    return {
      workflow_name: "flux2_txt2img",
      use_turbo: params.use_turbo ?? true,
    };
  }

  if (workflow === "flux2_editing") {
    return {
      workflow_name: "flux2_editing",
      use_turbo: params.use_turbo ?? true,
      ...(params.image_base64 ? { image_base64: params.image_base64 } : {}),
    };
  }

  if (workflow === "identidad_gguf") {
    return {
      workflow_name: "identidad_gguf",
      ...(params.image_url ? { image_url: params.image_url } : {}),
      ...(params.width ? { width: params.width } : {}),
      ...(params.height ? { height: params.height } : {}),
      ...(params.seed !== undefined ? { seed: params.seed } : {}),
    };
  }

  return { ...params };
}

function validatePrompt(value: string): string | undefined {
  if (value.trim().length === 0) {
    return "Prompt is required";
  }
  if (value.length > 1000) {
    return "Prompt must be 1000 characters or less";
  }
  return undefined;
}

function validateParameters(params: GenerationParameters): string | undefined {
  if (!params.workflow_name) {
    return "Please select a workflow";
  }
  if (!VALID_WORKFLOWS.includes(params.workflow_name)) {
    return "Invalid workflow";
  }
  return undefined;
}

function validateReferenceImage(
  params: GenerationParameters,
  referenceFaceUrl: string | null
): string | undefined {
  if (params.workflow_name === "identidad_gguf" && !referenceFaceUrl) {
    return "Reference image is required";
  }
  if (params.workflow_name === "flux2_editing" && !referenceFaceUrl) {
    return "Reference image is required";
  }
  return undefined;
}

export const useGenerationStore = create<GenerationStore>((set, get) => ({
  prompt: "",
  parameters: {},
  currentJob: null,
  generationState: "idle",
  sessionHistory: [],
  referenceFaceUrl: null,
  referenceGallery: [],
  errorMessage: null,
  validationErrors: {},
  _wsCleanup: null,

  setPrompt: (value: string) => {
    const promptError = validatePrompt(value);
    set({
      prompt: value,
      validationErrors: { ...get().validationErrors, prompt: promptError },
    });
  },

  setParameters: (value: Partial<GenerationParameters>) => {
    const newParams = normalizeParameters({ ...get().parameters, ...value });
    const paramsError = validateParameters(newParams);
    const referenceImageError = validateReferenceImage(
      newParams,
      get().referenceFaceUrl
    );
    set({
      parameters: newParams,
      validationErrors: {
        ...get().validationErrors,
        parameters: paramsError,
        referenceImage: referenceImageError,
      },
    });
  },

  setReferenceFaceUrl: (url: string) => {
    set({
      referenceFaceUrl: url,
      validationErrors: {
        ...get().validationErrors,
        referenceImage: validateReferenceImage(get().parameters, url),
      },
    });
  },

  addToGallery: (url: string) => {
    if (get().referenceGallery.includes(url)) return;
    set({
      referenceGallery: [url, ...get().referenceGallery],
    });
  },

  clearReferenceFace: () => {
    const parameters = { ...get().parameters };
    delete parameters.image_url;
    delete parameters.image_base64;
    set({
      referenceFaceUrl: null,
      parameters,
      validationErrors: {
        ...get().validationErrors,
        referenceImage: validateReferenceImage(parameters, null),
      },
    });
  },

  startConnecting: (jobId: string) => {
    set({
      generationState: "connecting",
      currentJob: {
        job_id: jobId,
        status: "connecting",
        progress: null,
        events: [],
      },
      errorMessage: null,
    });
  },

  addEvent: (event: JobEvent) => {
    const state = get();
    if (!state.currentJob) return;

    const updatedJob: CurrentJob = {
      ...state.currentJob,
      status: event.event,
      events: [...state.currentJob.events, event],
    };

    if (event.progress !== undefined && event.progress !== null) {
      updatedJob.progress = event.progress;
    }

    if (event.event === "completed" && event.result) {
      // Completed: prepend to sessionHistory, reset currentJob
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
        errorMessage: event.error?.detail ?? "Unknown error",
      });
      return;
    }

    if (event.event === "running") {
      set({
        generationState: "generating",
        currentJob: updatedJob,
      });
      return;
    }

    // pending or other events — just update the job
    set({ currentJob: updatedJob });
  },

  fail: (message: string) => {
    set({
      generationState: "error",
      currentJob: null,
      errorMessage: message,
    });
  },

  cancel: () => {
    const cleanup = get()._wsCleanup;
    cleanup?.();
    set({
      generationState: "idle",
      currentJob: null,
      errorMessage: null,
      _wsCleanup: null,
    });
  },

  reset: () => {
    const cleanup = get()._wsCleanup;
    cleanup?.();
    set({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      referenceFaceUrl: null,
      referenceGallery: [],
      errorMessage: null,
      validationErrors: {},
      _wsCleanup: null,
    });
  },
}));
