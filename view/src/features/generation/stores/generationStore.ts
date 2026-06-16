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
  ProductFormat,
  ValidationErrors,
  WorkflowName,
} from "../api/types";

interface GenerationStore {
  prompt: string;
  parameters: GenerationParameters;
  currentJob: CurrentJob | null;
  generationState: GenerationState;
  sessionHistory: HistoryItem[];
  referenceFaceUrl: string | null;
  errorMessage: string | null;
  validationErrors: ValidationErrors;
  /** Internal: WebSocket cleanup function (not reactive) */
  _wsCleanup: (() => void) | null;
  setPrompt(value: string): void;
  setParameters(value: Partial<GenerationParameters>): void;
  setReferenceFaceUrl(url: string): void;
  clearReferenceFace(): void;
  startConnecting(jobId: string): void;
  addEvent(event: JobEvent): void;
  fail(message: string): void;
  cancel(): void;
  reset(): void;
}

const VALID_WORKFLOWS: WorkflowName[] = [
  "txt2img",
  "qwen_txt2img",
  "img2img",
  "controlnet",
  "product_premium",
  "realistic_persona",
];

const PERSONA_FIELDS: Array<keyof GenerationParameters> = [
  "age",
  "gender",
  "ethnicity",
  "wardrobe",
  "expression",
  "background",
  "output_type",
  "image_url",
];

const PERSONA_STRING_FIELDS: Array<keyof GenerationParameters> = [
  "gender",
  "ethnicity",
  "wardrobe",
  "expression",
  "background",
  "output_type",
];

function removePersonaFields(params: GenerationParameters): GenerationParameters {
  const normalized = { ...params };
  for (const field of PERSONA_FIELDS) {
    delete normalized[field];
  }
  return normalized;
}

function removeEmptyPersonaStrings(params: GenerationParameters): GenerationParameters {
  const normalized = { ...params };
  for (const field of PERSONA_STRING_FIELDS) {
    if (normalized[field] === "") {
      delete normalized[field];
    }
  }
  return normalized;
}

function normalizeParameters(params: GenerationParameters): GenerationParameters {
  if (params.workflow_name === "product_premium") {
    const normalized = removePersonaFields({
      ...params,
      format: params.format ?? "square",
    });
    return normalized;
  }

  if (params.workflow_name === "realistic_persona") {
    const normalized = removeEmptyPersonaStrings(params);
    delete normalized.format;
    delete normalized.checkpoint_url;
    delete normalized.lora_url;
    return normalized;
  }

  const normalized = removePersonaFields(params);
  delete normalized.format;
  return normalized;
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
  if (
    params.workflow_name === "realistic_persona" &&
    params.age !== undefined &&
    (params.age < 18 || params.age > 100)
  ) {
    return "Age must be between 18 and 100";
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
    set({
      parameters: newParams,
      validationErrors: {
        ...get().validationErrors,
        parameters: paramsError,
      },
    });
  },

  setReferenceFaceUrl: (url: string) => {
    set({ referenceFaceUrl: url });
  },

  clearReferenceFace: () => {
    const parameters = { ...get().parameters };
    delete parameters.image_url;
    set({ referenceFaceUrl: null, parameters });
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
      errorMessage: null,
      validationErrors: {},
      _wsCleanup: null,
    });
  },
}));
