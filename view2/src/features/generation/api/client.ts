import type {
  GenerationParameters,
  JobEvent,
  SubmitGenerateResponse,
  WebSocketOptions,
} from "./types";

const FLUX2_WORKFLOWS = new Set<GenerationParameters["workflow_name"]>([
  "flux2_txt2img",
  "flux2_editing",
]);

export const DEFAULT_WS_RETRY_DELAY = 1000;
export const DEFAULT_WS_MAX_RETRIES = 3;

export async function submitGenerate(
  prompt: string,
  params: GenerationParameters
): Promise<SubmitGenerateResponse> {
  const payload: Record<string, unknown> = {
    prompt,
    workflow: params.workflow_name,
    workflow_name: params.workflow_name,
  };

  if (FLUX2_WORKFLOWS.has(params.workflow_name)) {
    payload.use_turbo = params.use_turbo ?? true;
  }

  if (params.workflow_name === "flux2_editing" && params.image_base64) {
    payload.image_base64 = params.image_base64;
  }

  if (params.workflow_name === "identidad_gguf") {
    payload.image_url = params.image_url;
    if (params.width !== undefined) payload.width = params.width;
    if (params.height !== undefined) payload.height = params.height;
    if (params.seed !== undefined) payload.seed = params.seed;
  }

  const response = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Generation request failed: ${response.status}`);
  }

  return response.json() as Promise<SubmitGenerateResponse>;
}

export function getWsUrl(jobId: string): string {
  return `/api/ws/generate/${encodeURIComponent(jobId)}`;
}

export function getImageUrl(jobId: string): string {
  return `/api/images/${encodeURIComponent(jobId)}`;
}

export function connectWebSocket(
  url: string,
  options: WebSocketOptions
): () => void {
  const {
    onEvent,
    onExhausted,
    maxRetries = DEFAULT_WS_MAX_RETRIES,
    retryDelay = DEFAULT_WS_RETRY_DELAY,
  } = options;

  let retries = 0;
  let cancelled = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let socket: WebSocket | null = null;

  const buildUrl = () => {
    if (typeof window === "undefined") {
      return `ws://localhost${url}`;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${url}`;
  };

  const connect = () => {
    if (cancelled) return;

    socket = new WebSocket(buildUrl());

    socket.onopen = () => undefined;

    socket.onmessage = (event) => {
      try {
        onEvent(JSON.parse(event.data as string) as JobEvent);
      } catch {
        // Ignore malformed messages.
      }
    };

    socket.onerror = () => undefined;

    socket.onclose = (event) => {
      if (cancelled || event.code === 1000) return;

      if (retries < maxRetries) {
        const delay = retryDelay * 2 ** retries;
        retries += 1;
        reconnectTimer = setTimeout(connect, delay);
        return;
      }

      onExhausted?.();
    };
  };

  connect();

  return () => {
    cancelled = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
    }
    socket?.close(1000, "User cancelled");
  };
}
