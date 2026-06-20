import { describe, expect, it } from "vitest";
import {
  GENERATION_STATES,
  JOB_EVENT_NAMES,
  WORKFLOW_NAMES,
  type GenerationState,
  type JobEvent,
  type WorkflowName,
} from "./types";

function assertExhaustive(event: JobEvent): JobEvent["event"] {
  switch (event.event) {
    case "booting_server":
    case "downloading_weights":
    case "generating":
    case "progress":
    case "completed":
    case "error":
      return event.event;
    default: {
      const neverEvent: never = event;
      return neverEvent;
    }
  }
}

describe("generation types", () => {
  it("keeps workflow names and generation states aligned to the design contract", () => {
    const workflows = [
      "flux2_txt2img",
      "flux2_editing",
      "identidad_gguf",
    ] as const satisfies readonly WorkflowName[];
    const states = [
      "idle",
      "booting",
      "downloadingWeights",
      "generating",
      "done",
      "error",
    ] as const satisfies readonly GenerationState[];

    expect(WORKFLOW_NAMES).toEqual(workflows);
    expect(GENERATION_STATES).toEqual(states);
  });

  it("keeps the backend event union exhaustive", () => {
    const events: JobEvent[] = [
      {
        event: "booting_server",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:00.000Z",
      },
      {
        event: "downloading_weights",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:01.000Z",
      },
      {
        event: "generating",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:02.000Z",
        progress: 12,
      },
      {
        event: "progress",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:03.000Z",
        progress: 58,
      },
      {
        event: "completed",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:04.000Z",
        result: { image_path: "/images/job-1.png" },
      },
      {
        event: "error",
        job_id: "job-1",
        timestamp: "2026-06-19T12:00:05.000Z",
        error: { code: "job_not_found", detail: "Missing job" },
      },
    ];

    expect(events.map(assertExhaustive)).toEqual(JOB_EVENT_NAMES);
  });
});
