import type { GenerationParameters } from "@/stores/generationStore";

interface SubmitGenerateResponse {
  job_id: string;
  status: string;
}

/**
 * Submit a generation request to the FastAPI backend.
 * POSTs { prompt, ...params } to /api/generate.
 */
export async function submitGenerate(
  prompt: string,
  params: GenerationParameters
): Promise<SubmitGenerateResponse> {
  const payload = {
    prompt,
    workflow: params.workflow_name,
    workflow_name: params.workflow_name,
    format: params.format ?? "square",
    checkpoint_url: params.checkpoint_url,
    lora_url: params.lora_url,
  };

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

/**
 * Build the WebSocket URL for streaming generation events.
 * Returns the relative path — the browser resolves it against the current origin.
 */
export function getWsUrl(jobId: string): string {
  return `/api/ws/generate/${jobId}`;
}

export function getImageUrl(jobId: string): string {
  return `/api/images/${encodeURIComponent(jobId)}`;
}

export interface WebSocketOptions {
  onEvent: (event: unknown) => void;
  onExhausted?: () => void;
  maxRetries?: number;
  retryDelay?: number;
}

/**
 * Connect to the WebSocket endpoint for a generation job.
 * Handles reconnection with exponential backoff (1s, 2s, 4s).
 * Per spec: retry up to 3 times, then call onExhausted.
 */
export function connectWebSocket(url: string, options: WebSocketOptions): () => void {
  const { onEvent, onExhausted, maxRetries = 3, retryDelay = 1000 } = options;
  let retries = 0;
  let ws: WebSocket | null = null;
  let cancelled = false;

  function connect() {
    if (cancelled) return;

    // Build absolute WebSocket URL
    const protocol = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost";
    const fullUrl = `${protocol}//${host}${url}`;

    ws = new WebSocket(fullUrl);

    ws.onopen = () => {
      // Reset retries on successful connection
      retries = 0;
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onEvent(parsed);
      } catch {
        // Non-JSON message — skip
      }
    };

    ws.onerror = () => {
      // Error handled by onclose
    };

    ws.onclose = (event) => {
      if (cancelled) return;

      // Don't retry on normal close (1000) or if the event was a completed/error
      if (event.code === 1000) return;

      if (retries < maxRetries) {
        retries++;
        const delay = retryDelay * Math.pow(2, retries - 1); // 1s, 2s, 4s
        setTimeout(connect, delay);
      } else {
        onExhausted?.();
      }
    };
  }

  connect();

  return () => {
    cancelled = true;
    ws?.close(1000, "User cancelled");
  };
}
