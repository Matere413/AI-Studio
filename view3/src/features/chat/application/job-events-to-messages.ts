// ─── Job Events → Chat Messages ────────────────────────────────
// Pure function that transforms a stream of JobEvent[] into
// ChatMessage[] suitable for rendering in the MessageList component.
// Each event type maps to a specific message format.

import type { JobEvent } from "../../studio/domain/dto.ts";
import type { ChatMessage } from "../domain/chat-message.ts";

/**
 * Transform an array of JobEvent frames into display-ready ChatMessages.
 *
 * - `booting_server` / `downloading_weights` / `generating` → event message
 * - `progress` → progress message with percentage
 * - `completed` → result message with proxy image URL
 * - `error` → error message with details
 */
export function jobEventsToChatMessages(events: JobEvent[]): ChatMessage[] {
  return events.map((event) => eventToMessage(event));
}

function eventToMessage(event: JobEvent): ChatMessage {
  const base: Omit<ChatMessage, "type" | "text"> = {
    id: `${event.job_id}-${event.timestamp}-${event.event}`,
    role: "agent",
    timestamp: event.timestamp,
  };

  switch (event.event) {
    case "booting_server":
      return { ...base, type: "event", text: "Booting server..." };

    case "downloading_weights":
      return { ...base, type: "event", text: "Downloading model weights..." };

    case "generating":
      return { ...base, type: "event", text: "Generating..." };

    case "progress":
      return {
        ...base,
        type: "progress",
        text: `Progress: ${event.progress ?? 0}%`,
        progress: event.progress ?? 0,
      };

    case "completed":
      return {
        ...base,
        type: "result",
        text: "Image generated successfully",
        imageUrl: `/api/images/${event.job_id}`,
      };

    case "error":
      return {
        ...base,
        type: "error",
        text: event.error
          ? `${event.error.code === "generation_failed" ? "Generation failed" : event.error.code}: ${event.error.detail}`
          : "An error occurred during generation",
        error: event.error
          ? { code: event.error.code, detail: event.error.detail }
          : { code: "unknown", detail: "An error occurred during generation" },
      };
  }
}
