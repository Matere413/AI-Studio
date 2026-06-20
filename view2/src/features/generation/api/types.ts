export type WorkflowName =
  | "flux2_txt2img"
  | "flux2_editing"
  | "identidad_gguf";

export const WORKFLOW_NAMES = [
  "flux2_txt2img",
  "flux2_editing",
  "identidad_gguf",
] as const satisfies readonly WorkflowName[];

export type GenerationState =
  | "idle"
  | "booting"
  | "downloadingWeights"
  | "generating"
  | "done"
  | "error";

export const GENERATION_STATES = [
  "idle",
  "booting",
  "downloadingWeights",
  "generating",
  "done",
  "error",
] as const satisfies readonly GenerationState[];

export type JobEventName =
  | "booting_server"
  | "downloading_weights"
  | "generating"
  | "progress"
  | "completed"
  | "error";

export const JOB_EVENT_NAMES = [
  "booting_server",
  "downloading_weights",
  "generating",
  "progress",
  "completed",
  "error",
] as const satisfies readonly JobEventName[];

export interface GenerationParameters {
  workflow_name: WorkflowName;
  use_turbo?: boolean;
  image_base64?: string;
  image_url?: string;
  width?: number;
  height?: number;
  seed?: number;
}

export interface SubmitGenerateResponse {
  job_id: string;
  status: string;
}

export interface WebSocketOptions {
  onEvent: (event: JobEvent) => void;
  onExhausted?: () => void;
  maxRetries?: number;
  retryDelay?: number;
}

interface BaseJobEvent {
  job_id: string;
  timestamp: string;
  message?: string | null;
}

export type JobEvent =
  | (BaseJobEvent & {
      event: "booting_server";
      progress?: null;
    })
  | (BaseJobEvent & {
      event: "downloading_weights";
      progress?: null;
    })
  | (BaseJobEvent & {
      event: "generating";
      progress: number;
    })
  | (BaseJobEvent & {
      event: "progress";
      progress: number;
    })
  | (BaseJobEvent & {
      event: "completed";
      result: { image_path: string };
    })
  | (BaseJobEvent & {
      event: "error";
      error: { code: string; detail: string };
    });
