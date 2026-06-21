// ─── Chat Message Type ─────────────────────────────────────────
// UI-facing type that combines user inputs with job events.
// Replaces MockMessage in the presentation layer.

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  timestamp: string;
  type: "text" | "progress" | "event" | "result" | "error";
  /** Progress percentage 0–100 (only for progress type). */
  progress?: number;
  /** Proxy image URL (only for result type). */
  imageUrl?: string;
  /** Error info (only for error type). */
  error?: { code: string; detail: string };
}
