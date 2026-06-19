import type {
  GenerationParameters,
  SubmitGenerateResponse,
  WebSocketOptions,
} from "./types";

const FLUX_WORKFLOWS = new Set(["flux2_txt2img", "flux2_editing"]);

export async function submitGenerate(
  prompt: string,
  params: GenerationParameters
): Promise<SubmitGenerateResponse> {
  const payload: Record<string, unknown> = {
    prompt,
    workflow: params.workflow_name,
    workflow_name: params.workflow_name,
  };

  if (FLUX_WORKFLOWS.has(params.workflow_name ?? "")) {
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

  return response.json();
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
  const { onEvent, onExhausted, maxRetries = 3, retryDelay = 1000 } = options;
  let retries = 0;
  let socket: WebSocket | null = null;
  let cancelled = false;

  const resolveUrl = () => {
    if (url.startsWith("ws://") || url.startsWith("wss://")) return url;
    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? "wss:"
        : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost";
    return `${protocol}//${host}${url}`;
  };

  const connect = () => {
    if (cancelled) return;
    socket = new WebSocket(resolveUrl());

    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data));
      } catch {
        // Ignore non-JSON frames from proxies or server keepalives.
      }
    };

    socket.onclose = (event) => {
      if (cancelled || event.code === 1000) return;
      if (retries >= maxRetries) {
        onExhausted?.();
        return;
      }

      const delay = retryDelay * Math.pow(2, retries);
      retries += 1;
      window.setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    cancelled = true;
    socket?.close(1000, "User cancelled");
  };
}
