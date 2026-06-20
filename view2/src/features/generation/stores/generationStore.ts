import { create } from "zustand";
import { getImageUrl } from "../api/client";
import {
  WORKFLOW_NAMES,
  type GenerationParameters,
  type GenerationState,
  type JobEvent,
  type JobEventName,
  type WorkflowName,
} from "../api/types";

export type { GenerationParameters, GenerationState, JobEvent, JobEventName, WorkflowName };

export interface HistoryItem {
  id: string;
  imagePath: string;
  prompt: string;
  parameters: Partial<GenerationParameters>;
  completedAt: string;
}

export interface ValidationErrors {
  prompt?: string;
  parameters?: string;
  referenceImage?: string;
}

export interface CurrentJob {
  job_id: string;
  status: JobEventName | "connecting";
  progress: number | null;
  events: JobEvent[];
}

interface GenerationStore {
  prompt: string;
  parameters: Partial<GenerationParameters>;
  currentJob: CurrentJob | null;
  terminalEvent: JobEvent | null;
  generationState: GenerationState;
  sessionHistory: HistoryItem[];
  referenceFaceUrl: string | null;
  referenceGallery: string[];
  errorMessage: string | null;
  validationErrors: ValidationErrors;
  _wsCleanup: (() => void) | null;
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  setReferenceFaceUrl(url: string | null): void;
  addToGallery(url: string): void;
  removeFromGallery(url: string): void;
  clearReferenceFace(): void;
  startConnecting(jobId: string): void;
  addEvent(event: JobEvent): void;
  fail(message: string): void;
  cancel(): void;
  reset(): void;
}

const VALID_WORKFLOWS = new Set<WorkflowName>(WORKFLOW_NAMES);
const PROMPT_MAX_LENGTH = 1000;

function normalizeParameters(
  params: Partial<GenerationParameters>
): Partial<GenerationParameters> {
  const workflow = params.workflow_name;

  if (workflow === "flux2_txt2img") {
    return {
      workflow_name: workflow,
      use_turbo: params.use_turbo ?? true,
    };
  }

  if (workflow === "flux2_editing") {
    return {
      workflow_name: workflow,
      use_turbo: params.use_turbo ?? true,
      ...(params.image_base64 ? { image_base64: params.image_base64 } : {}),
    };
  }

  if (workflow === "identidad_gguf") {
    return {
      workflow_name: workflow,
      ...(params.image_url ? { image_url: params.image_url } : {}),
      ...(params.width !== undefined ? { width: params.width } : {}),
      ...(params.height !== undefined ? { height: params.height } : {}),
      ...(params.seed !== undefined ? { seed: params.seed } : {}),
    };
  }

  return { ...params };
}

function validatePrompt(value: string): string | undefined {
  if (value.trim().length === 0) {
    return "Prompt is required";
  }

  if (value.length > PROMPT_MAX_LENGTH) {
    return `Prompt must be ${PROMPT_MAX_LENGTH} characters or less`;
  }

  return undefined;
}

function validateParameters(
  params: Partial<GenerationParameters>
): string | undefined {
  if (!params.workflow_name) {
    return "Please select a workflow";
  }

  if (!VALID_WORKFLOWS.has(params.workflow_name as WorkflowName)) {
    return "Invalid workflow";
  }

  return undefined;
}

function validateReferenceImage(
  params: Partial<GenerationParameters>,
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

export const useGenerationStore = create<GenerationStore>((set, get) => ({
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

  setPrompt(value) {
    set((state) => ({
      prompt: value,
      validationErrors: {
        ...state.validationErrors,
        prompt: validatePrompt(value),
      },
    }));
  },

  setParameters(value) {
    const parameters = normalizeParameters({ ...get().parameters, ...value });

    set((state) => ({
      parameters,
      validationErrors: {
        ...state.validationErrors,
        parameters: validateParameters(parameters),
        referenceImage: validateReferenceImage(parameters, state.referenceFaceUrl),
      },
    }));
  },

  setReferenceFaceUrl(url) {
    set((state) => ({
      referenceFaceUrl: url,
      validationErrors: {
        ...state.validationErrors,
        referenceImage: validateReferenceImage(state.parameters, url),
      },
    }));
  },

  addToGallery(url) {
    if (get().referenceGallery.includes(url)) return;

    set({
      referenceGallery: [url, ...get().referenceGallery],
    });
  },

  removeFromGallery(url) {
    set((state) => ({
      referenceGallery: state.referenceGallery.filter((item) => item !== url),
    }));

    if (get().referenceFaceUrl === url) {
      get().clearReferenceFace();
    }
  },

  clearReferenceFace() {
    set((state) => {
      const parameters = { ...state.parameters };
      delete parameters.image_url;
      delete parameters.image_base64;

      return {
        referenceFaceUrl: null,
        parameters,
        validationErrors: {
          ...state.validationErrors,
          referenceImage: validateReferenceImage(parameters, null),
        },
      };
    });
  },

  startConnecting(jobId) {
    set({
      generationState: "booting",
      terminalEvent: null,
      currentJob: {
        job_id: jobId,
        status: "connecting",
        progress: null,
        events: [],
      },
      errorMessage: null,
    });
  },

  addEvent(event) {
    const state = get();

    if (!state.currentJob || state.currentJob.job_id !== event.job_id) return;

    const updatedJob: CurrentJob = {
      ...state.currentJob,
      status: event.event,
      events: [...state.currentJob.events, event],
    };

    if ("progress" in event && typeof event.progress === "number") {
      updatedJob.progress = event.progress;
    }

    if (event.event === "booting_server") {
      set({
        generationState: "booting",
        currentJob: updatedJob,
        terminalEvent: null,
        errorMessage: null,
      });
      return;
    }

    if (event.event === "downloading_weights") {
      set({
        generationState: "downloadingWeights",
        currentJob: updatedJob,
        terminalEvent: null,
        errorMessage: null,
      });
      return;
    }

    if (event.event === "generating" || event.event === "progress") {
      set({
        generationState: "generating",
        currentJob: updatedJob,
        terminalEvent: null,
        errorMessage: null,
      });
      return;
    }

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
        terminalEvent: event,
        sessionHistory: [historyItem, ...state.sessionHistory],
        errorMessage: null,
      });
      return;
    }

    if (event.event === "error") {
      set({
        generationState: "error",
        currentJob: null,
        terminalEvent: event,
        errorMessage: event.error.detail,
      });
      return;
    }

    set({
      currentJob: updatedJob,
      terminalEvent: null,
    });
  },

  fail(message) {
    set({
      generationState: "error",
      currentJob: null,
      terminalEvent: null,
      errorMessage: message,
    });
  },

  cancel() {
    const cleanup = get()._wsCleanup;
    cleanup?.();

    set({
      generationState: "idle",
      currentJob: null,
      terminalEvent: null,
      errorMessage: null,
      _wsCleanup: null,
    });
  },

  reset() {
    const cleanup = get()._wsCleanup;
    cleanup?.();

    set({
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
  },
}));
