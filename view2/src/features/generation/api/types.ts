export const WORKFLOW_NAMES = [
  "flux2_txt2img",
  "flux2_editing",
  "identidad_gguf",
] as const;

export const JOB_EVENT_NAMES = [
  "booting_server",
  "downloading_weights",
  "generating",
  "progress",
  "completed",
  "error",
] as const;

export type WorkflowName = (typeof WORKFLOW_NAMES)[number];

export type JobEventName = (typeof JOB_EVENT_NAMES)[number];

export type GenerationState =
  | "idle"
  | "booting"
  | "downloadingWeights"
  | "generating"
  | "done"
  | "error";

export interface GenerationParameters {
  workflow_name?: WorkflowName;
  use_turbo?: boolean;
  image_base64?: string;
  image_url?: string;
  width?: number;
  height?: number;
  seed?: number;
}

export interface JobEvent {
  event: JobEventName;
  job_id: string;
  timestamp: string;
  progress?: number | null;
  message?: string | null;
  result?: { image_path: string } | null;
  error?: { code: string; detail: string } | null;
}

export interface CurrentJob {
  job_id: string;
  status: JobEventName | "connecting";
  progress: number | null;
  events: JobEvent[];
  errorMessage?: string;
}

export interface HistoryItem {
  id: string;
  imagePath: string;
  prompt: string;
  parameters: GenerationParameters;
  completedAt: string;
}

export interface SubmitGenerateResponse {
  job_id: string;
  status: "pending" | string;
}

export interface ValidationErrors {
  prompt?: string;
  parameters?: string;
  referenceImage?: string;
}

export interface WebSocketOptions {
  onEvent: (event: unknown) => void;
  onExhausted?: () => void;
  maxRetries?: number;
  retryDelay?: number;
}
