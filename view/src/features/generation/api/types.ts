export type GenerationState =
  | "idle"
  | "connecting"
  | "generating"
  | "done"
  | "error";

export type WorkflowName =
  | "txt2img"
  | "img2img"
  | "controlnet"
  | "product_premium";

export type ProductFormat = "square" | "vertical";

export interface GenerationParameters {
  workflow_name?: WorkflowName;
  format?: ProductFormat;
  checkpoint_url?: string;
  lora_url?: string;
}

export interface JobEvent {
  event: "pending" | "running" | "completed" | "error";
  job_id: string;
  timestamp: string;
  progress?: number | null;
  message?: string | null;
  result?: { image_path: string } | null;
  error?: { code: string; detail: string } | null;
}

export interface CurrentJob {
  job_id: string;
  status: JobEvent["event"] | "connecting";
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

export interface ValidationErrors {
  prompt?: string;
  parameters?: string;
}

export interface SubmitGenerateResponse {
  job_id: string;
  status: string;
}

export interface WebSocketOptions {
  onEvent: (event: unknown) => void;
  onExhausted?: () => void;
  maxRetries?: number;
  retryDelay?: number;
}
