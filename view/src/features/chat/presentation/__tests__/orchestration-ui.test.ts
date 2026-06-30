import { describe, it } from "node:test";
import assert from "node:assert";

import {
  getSafeOrchestrationMessage,
  getSidebarTabs,
  getStageTimelineItems,
  shouldShowManualControls,
} from "../components/orchestration-ui.ts";

void describe("orchestration sidebar UI state", () => {
  void it("keeps Chat and Manual tabs with Chat selected by default", () => {
    const tabs = getSidebarTabs("chat");

    assert.deepStrictEqual(tabs, [
      { id: "chat", label: "Chat", selected: true },
      { id: "manual", label: "Manual", selected: false },
    ]);
  });

  void it("hides manual workflow controls in the prompt-first Chat tab", () => {
    assert.strictEqual(shouldShowManualControls("chat"), false);
    assert.strictEqual(shouldShowManualControls("manual"), true);
  });

  void it("formats backend stage responses for the visible timeline", () => {
    const items = getStageTimelineItems([
      { name: "planning", status: "completed" },
      { name: "validating_assets", status: "blocked" },
    ]);

    assert.deepStrictEqual(items, [
      { label: "Planning", status: "Completed" },
      { label: "Validating assets", status: "Blocked" },
    ]);
  });

  void it("shows the full planned chain before the backend returns stages", () => {
    const items = getStageTimelineItems([]);

    assert.deepStrictEqual(items, [
      { label: "Planning", status: "Pending" },
      { label: "Validating assets", status: "Pending" },
      { label: "Dispatching", status: "Pending" },
      { label: "Generating", status: "Pending" },
    ]);
  });

  void it("hides raw orchestration error details from user-facing copy", () => {
    const message = getSafeOrchestrationMessage({
      outcome: "error",
      error_code: "planner_provider_invalid_response",
      error_detail: "Traceback: provider timeout at internal host",
      stages: [{ name: "planning", status: "blocked" }],
    });

    assert.strictEqual(message, "The planning service returned an invalid response. Please try again.");
  });
});
