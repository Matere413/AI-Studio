export type GenerationState =
  | "idle"
  | "connecting"
  | "generating"
  | "done"
  | "error";

export type WorkflowName =
  | "txt2img"
  | "qwen_txt2img"
  | "img2img"
  | "controlnet"
  | "product_premium"
  | "realistic_persona"
  | "identidad_gguf";

export type ProductFormat = "square" | "vertical";
export type PersonaOutputType = "portrait" | "full-body" | "lifestyle" | "editorial";

export interface GenerationParameters {
  workflow_name?: WorkflowName;
  format?: ProductFormat;
  quality_mode?: "fast" | "high";
  width?: number;
  height?: number;
  checkpoint_url?: string;
  lora_url?: string;
  age?: number;
  gender?: string;
  ethnicity?: string;
  wardrobe?: string;
  expression?: string;
  background?: string;
  output_type?: PersonaOutputType;
  image_url?: string;
  seed?: number;
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
  referenceImage?: string;
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
