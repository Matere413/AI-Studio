// ─── Unit Tests: Job Events → Chat Messages ────────────────────
// Tests the pure function that transforms JobEvent[] into ChatMessage[].
// Each event type maps to a specific message type and visible text.

import { describe, it } from "node:test";
import assert from "node:assert";
import { jobEventsToChatMessages } from "../job-events-to-messages.ts";
import type { JobEvent } from "../../../studio/domain/dto.ts";

void describe("jobEventsToChatMessages", () => {
  void it("returns empty array for empty input", () => {
    const result = jobEventsToChatMessages([]);
    assert.strictEqual(result.length, 0);
  });

  void it("converts booting_server event to an event message", () => {
    const events: JobEvent[] = [
      { event: "booting_server", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "event");
    assert.strictEqual(result[0].role, "agent");
    assert.strictEqual(result[0].text, "Booting server...");
    assert.strictEqual(result[0].timestamp, "2026-01-01T00:00:00Z");
    assert.ok(typeof result[0].id === "string" && result[0].id.length > 0);
  });

  void it("converts downloading_weights event to an event message", () => {
    const events: JobEvent[] = [
      { event: "downloading_weights", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "event");
    assert.strictEqual(result[0].text, "Downloading model weights...");
  });

  void it("converts generating event to an event message", () => {
    const events: JobEvent[] = [
      { event: "generating", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "event");
    assert.strictEqual(result[0].text, "Generating...");
  });

  void it("converts progress event to a progress message with percentage", () => {
    const events: JobEvent[] = [
      { event: "progress", job_id: "j1", timestamp: "2026-01-01T00:00:00Z", progress: 42 },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "progress");
    assert.strictEqual(result[0].progress, 42);
    assert.strictEqual(result[0].text, "Progress: 42%");
  });

  void it("converts completed event to a result message with image URL", () => {
    const events: JobEvent[] = [
      {
        event: "completed",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        result: { image_path: "/media/output.png" },
      },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "result");
    assert.strictEqual(result[0].imageUrl, "/api/images/j1");
    assert.strictEqual(result[0].text, "Image generated successfully");
  });

  void it("converts completed event without result to text-only message", () => {
    const events: JobEvent[] = [
      { event: "completed", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "result");
    // Even without result data, the proxy URL is still available
    assert.strictEqual(result[0].imageUrl, "/api/images/j1");
  });

  void it("converts error event to an error message", () => {
    const events: JobEvent[] = [
      {
        event: "error",
        job_id: "j1",
        timestamp: "2026-01-01T00:00:00Z",
        error: { code: "generation_failed", detail: "GPU out of memory" },
      },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "error");
    assert.strictEqual(result[0].role, "agent");
    assert.strictEqual(result[0].text, "Generation failed: GPU out of memory");
    assert.deepStrictEqual(result[0].error, { code: "generation_failed", detail: "GPU out of memory" });
  });

  void it("converts multiple events in order", () => {
    const events: JobEvent[] = [
      { event: "booting_server", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
      { event: "downloading_weights", job_id: "j1", timestamp: "2026-01-01T00:00:01Z" },
      { event: "generating", job_id: "j1", timestamp: "2026-01-01T00:00:02Z" },
      { event: "progress", job_id: "j1", timestamp: "2026-01-01T00:00:03Z", progress: 80 },
      { event: "completed", job_id: "j1", timestamp: "2026-01-01T00:00:04Z", result: { image_path: "/media/out.png" } },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 5);
    assert.strictEqual(result[0].type, "event");
    assert.strictEqual(result[0].text, "Booting server...");
    assert.strictEqual(result[1].text, "Downloading model weights...");
    assert.strictEqual(result[2].text, "Generating...");
    assert.strictEqual(result[3].type, "progress");
    assert.strictEqual(result[3].progress, 80);
    assert.strictEqual(result[4].type, "result");
    assert.strictEqual(result[4].imageUrl, "/api/images/j1");
  });

  void it("converts error event without error details gracefully", () => {
    const events: JobEvent[] = [
      { event: "error", job_id: "j1", timestamp: "2026-01-01T00:00:00Z" },
    ];
    const result = jobEventsToChatMessages(events);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].type, "error");
    assert.strictEqual(result[0].text, "An error occurred during generation");
  });
});
