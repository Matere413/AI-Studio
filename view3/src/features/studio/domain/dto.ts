// ─── Studio Domain DTOs ───────────────────────────────────────
// Response and event types for the generation lifecycle.
// Maps exactly to the Python backend models.

// ─── Generate Response ────────────────────────────────────────

/**
 * Response returned by `POST /generate` on success.
 */
export interface GenerateResponse {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
}

// ─── Job Event Types ──────────────────────────────────────────

/**
 * Result payload attached to a completed job event.
 */
export interface JobEventResult {
  /** Path (relative to the backend media root) to the generated image. */
  image_path: string;
}

/**
 * Error payload attached to a failed job event.
 */
export interface JobEventError {
  code: string;
  detail: string;
}

/**
 * Single event frame delivered over the generation WebSocket.
 *
 * Mirrors `api/src/features/generation/models.py::JobEvent` exactly:
 *
 * | `event` value         | Description                        |
 * |-----------------------|------------------------------------|
 * | `booting_server`      | Modal container is starting up     |
 * | `downloading_weights` | Model weights are being cached     |
 * | `generating`          | ComfyUI is executing the workflow  |
 * | `progress`            | Progress percentage update         |
 * | `completed`           | Terminal — job succeeded           |
 * | `error`               | Terminal — job failed              |
 *
 * - `progress`: set when `event` is `"progress"` (0–100)
 * - `result`: set when `event` is `"completed"`
 * - `error`: set when `event` is `"error"`
 */
export interface JobEvent {
  event:
    | "booting_server"
    | "downloading_weights"
    | "generating"
    | "progress"
    | "completed"
    | "error";
  job_id: string;
  timestamp: string;
  /** Progress percentage 0–100 (set for progress events). */
  progress?: number;
  /** Human-readable message (set for informative events). */
  message?: string;
  /** Result payload (set when event is `"completed"`). */
  result?: JobEventResult;
  /** Error payload (set when event is `"error"`). */
  error?: JobEventError;
}
