import { describe, it, expect, beforeEach } from "vitest";
import {
  useGenerationStore,
  type GenerationParameters,
  type WorkflowName,
} from "./generationStore";

describe("generationStore", () => {
  beforeEach(() => {
    // Reset store to defaults before each test
    useGenerationStore.setState({
      prompt: "",
      parameters: {},
      currentJob: null,
      generationState: "idle",
      sessionHistory: [],
      validationErrors: {},
      errorMessage: null,
      _wsCleanup: null,
    });
  });

  describe("defaults (Spec: Zustand Store Contract — Scenario: Defaults)", () => {
    it("initializes with empty prompt", () => {
      const state = useGenerationStore.getState();
      expect(state.prompt).toBe("");
    });

    it("initializes with default parameters (Spec: Zustand Store Contract — Scenario: Defaults)", () => {
      const state = useGenerationStore.getState();
      expect(state.parameters).toEqual({});
    });

    it("initializes with null currentJob", () => {
      const state = useGenerationStore.getState();
      expect(state.currentJob).toBeNull();
    });

    it("initializes with idle state", () => {
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("idle");
    });

    it("initializes with empty sessionHistory", () => {
      const state = useGenerationStore.getState();
      expect(state.sessionHistory).toEqual([]);
    });
  });

  describe("setPrompt (Spec: Form Validation — Scenario: Valid submission)", () => {
    it("updates the prompt value", () => {
      useGenerationStore.getState().setPrompt("A fiery sunset over mountains");
      expect(useGenerationStore.getState().prompt).toBe(
        "A fiery sunset over mountains"
      );
    });

    it("validates empty prompt as error", () => {
      useGenerationStore.getState().setPrompt("");
      expect(useGenerationStore.getState().validationErrors.prompt).toBe(
        "Prompt is required"
      );
    });

    it("validates whitespace-only prompt as error", () => {
      useGenerationStore.getState().setPrompt("   ");
      expect(useGenerationStore.getState().validationErrors.prompt).toBe(
        "Prompt is required"
      );
    });

    it("validates prompt exceeding 1000 chars", () => {
      useGenerationStore.getState().setPrompt("x".repeat(1001));
      expect(useGenerationStore.getState().validationErrors.prompt).toBe(
        "Prompt must be 1000 characters or less"
      );
    });

    it("accepts prompt at exactly 1000 chars", () => {
      useGenerationStore.getState().setPrompt("x".repeat(1000));
      expect(useGenerationStore.getState().validationErrors.prompt).toBeUndefined();
    });

    it("clears prompt error when valid prompt is set", () => {
      useGenerationStore.getState().setPrompt("");
      expect(useGenerationStore.getState().validationErrors.prompt).toBeDefined();
      useGenerationStore.getState().setPrompt("Valid prompt");
      expect(useGenerationStore.getState().validationErrors.prompt).toBeUndefined();
    });
  });

  describe("setParameters (Spec: Form validation — Scenario: Invalid parameter)", () => {
    it("updates parameters partially", () => {
      useGenerationStore.getState().setParameters({ workflow_name: "txt2img" });
      useGenerationStore.getState().setParameters({ checkpoint_url: "http://example.com/model.safetensors" });
      expect(useGenerationStore.getState().parameters).toEqual({
        workflow_name: "txt2img",
        checkpoint_url: "http://example.com/model.safetensors",
      });
    });

    it("validates invalid workflow_name", () => {
      useGenerationStore.getState().setParameters({ workflow_name: "invalid_workflow" as unknown as WorkflowName });
      expect(useGenerationStore.getState().validationErrors.parameters).toBe(
        "Invalid workflow"
      );
    });

    it("validates missing workflow_name", () => {
      useGenerationStore.getState().setParameters({});
      expect(useGenerationStore.getState().validationErrors.parameters).toBe(
        "Please select a workflow"
      );
    });

    it("accepts valid workflow names", () => {
      for (const name of ["txt2img", "img2img", "controlnet"] as const) {
        useGenerationStore.setState({ parameters: {} });
        useGenerationStore.getState().setParameters({ workflow_name: name });
        expect(useGenerationStore.getState().validationErrors.parameters).toBeUndefined();
      }
    });
  });

  describe("product_premium workflow (Spec: Product workflow controls)", () => {
    it("accepts product_premium without an explicit format", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "product_premium" as WorkflowName,
      } as unknown as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().validationErrors.parameters).toBeUndefined();
      expect(useGenerationStore.getState().parameters).toMatchObject({
        workflow_name: "product_premium",
      });
    });

    it("accepts product_premium with vertical format", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "product_premium" as WorkflowName,
        format: "vertical",
      } as unknown as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().validationErrors.parameters).toBeUndefined();
      expect(useGenerationStore.getState().parameters).toMatchObject({
        workflow_name: "product_premium",
        format: "vertical",
      });
    });
  });

  describe("realistic_persona workflow (Spec: Realistic Persona Workflow UI Controls)", () => {
    it("accepts valid persona controls and preserves their typed values", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "realistic_persona",
        age: 42,
        gender: "woman",
        ethnicity: "latina",
        wardrobe: "tailored linen suit",
        expression: "confident half-smile",
        background: "warm editorial studio",
        output_type: "portrait",
      } as unknown as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().validationErrors.parameters).toBeUndefined();
      expect(useGenerationStore.getState().parameters).toMatchObject({
        workflow_name: "realistic_persona",
        age: 42,
        gender: "woman",
        ethnicity: "latina",
        wardrobe: "tailored linen suit",
        expression: "confident half-smile",
        background: "warm editorial studio",
        output_type: "portrait",
      });
    });

    it("validates persona age outside the 18-100 range", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "realistic_persona",
        age: 17,
      } as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().validationErrors.parameters).toBe(
        "Age must be between 18 and 100"
      );
    });

    it("removes model and product-only fields from persona parameters", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "txt2img",
        checkpoint_url: "https://example.com/model.safetensors",
        lora_url: "https://example.com/lora.safetensors",
      });
      useGenerationStore.getState().setParameters({
        workflow_name: "realistic_persona",
        age: 35,
        format: "vertical",
        output_type: "editorial",
      } as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().parameters).toEqual({
        workflow_name: "realistic_persona",
        age: 35,
        output_type: "editorial",
      });
    });

    it("removes empty persona select values so defaults can apply", () => {
      useGenerationStore.getState().setParameters({
        workflow_name: "realistic_persona",
        gender: "woman",
        ethnicity: "latina",
        wardrobe: "linen blazer",
        expression: "soft smile",
        background: "warm studio",
        output_type: "portrait",
      } as Partial<GenerationParameters>);

      useGenerationStore.getState().setParameters({
        workflow_name: "realistic_persona",
        gender: "",
        ethnicity: "",
        wardrobe: "",
        expression: "",
        background: "",
        output_type: "",
      } as unknown as Partial<GenerationParameters>);

      expect(useGenerationStore.getState().parameters).toEqual({
        workflow_name: "realistic_persona",
      });
    });
  });

  describe("startConnecting (Spec: State Machine — Scenario: Full lifecycle)", () => {
    it("transitions to connecting state with job_id", () => {
      useGenerationStore.getState().startConnecting("job-123");
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("connecting");
      expect(state.currentJob).not.toBeNull();
      expect(state.currentJob!.job_id).toBe("job-123");
      expect(state.currentJob!.status).toBe("connecting");
      expect(state.currentJob!.progress).toBeNull();
      expect(state.currentJob!.events).toEqual([]);
    });
  });

  describe("addEvent (Spec: State Machine — Scenarios: Full lifecycle + Failure)", () => {
    it("transitions to generating on running event", () => {
      useGenerationStore.getState().startConnecting("job-abc");
      useGenerationStore.getState().addEvent({
        event: "running",
        job_id: "job-abc",
        timestamp: "2024-01-01T00:00:00Z",
      });
      expect(useGenerationStore.getState().generationState).toBe("generating");
      expect(useGenerationStore.getState().currentJob!.status).toBe("running");
    });

    it("transitions to done on completed event with result, prepends to history", () => {
      useGenerationStore.getState().startConnecting("job-done");
      useGenerationStore.getState().addEvent({
        event: "running",
        job_id: "job-done",
        timestamp: "2024-01-01T00:00:00Z",
      });
      useGenerationStore.getState().addEvent({
        event: "completed",
        job_id: "job-done",
        timestamp: "2024-01-01T00:01:00Z",
        result: { image_path: "/images/output.png" },
      });
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("done");
      expect(state.currentJob).toBeNull();
      expect(state.sessionHistory).toHaveLength(1);
      expect(state.sessionHistory[0].imagePath).toBe("/api/images/job-done");
      expect(state.sessionHistory[0].prompt).toBe(useGenerationStore.getState().prompt);
    });

    it("transitions to error on error event (Spec: State Machine — Scenario: Failure)", () => {
      useGenerationStore.getState().startConnecting("job-err");
      useGenerationStore.getState().addEvent({
        event: "error",
        job_id: "job-err",
        timestamp: "2024-01-01T00:00:00Z",
        error: { code: "SERVER_ERROR", detail: "Something went wrong" },
      });
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("error");
      expect(state.errorMessage).toBe("Something went wrong");
    });

    it("updates progress on event with progress field (Spec: Cold Start — Scenario: Becomes determinate)", () => {
      useGenerationStore.getState().startConnecting("job-prog");
      useGenerationStore.getState().addEvent({
        event: "running",
        job_id: "job-prog",
        timestamp: "2024-01-01T00:00:00Z",
        progress: 42,
      });
      expect(useGenerationStore.getState().currentJob!.progress).toBe(42);
    });
  });

  describe("cancel (Spec: State Machine — Scenario: Cancel)", () => {
    it("resets to idle and clears currentJob", () => {
      useGenerationStore.getState().startConnecting("job-cancel");
      useGenerationStore.getState().cancel();
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("idle");
      expect(state.currentJob).toBeNull();
    });
  });

  describe("fail (Spec: State Machine — Scenario: Failure)", () => {
    it("transitions to error state with message", () => {
      useGenerationStore.getState().startConnecting("job-fail");
      useGenerationStore.getState().fail("Connection lost — please try again");
      const state = useGenerationStore.getState();
      expect(state.generationState).toBe("error");
      expect(state.errorMessage).toBe("Connection lost — please try again");
      expect(state.currentJob).toBeNull();
    });
  });

  describe("reset", () => {
    it("resets all state to defaults", () => {
      useGenerationStore.getState().setPrompt("test prompt");
      useGenerationStore.getState().startConnecting("job-reset");
      useGenerationStore.getState().addEvent({
        event: "running",
        job_id: "job-reset",
        timestamp: "2024-01-01T00:00:00Z",
      });
      useGenerationStore.getState().reset();
      const state = useGenerationStore.getState();
      expect(state.prompt).toBe("");
      expect(state.generationState).toBe("idle");
      expect(state.currentJob).toBeNull();
      expect(state.sessionHistory).toEqual([]);
    });
  });

  describe("completed-to-history behavior (Spec: Store Contract — Scenario: Completed to history)", () => {
    it("prepends newest item first in sessionHistory", () => {
      // First completed job
      useGenerationStore.getState().startConnecting("job-1");
      useGenerationStore.getState().addEvent({
        event: "completed",
        job_id: "job-1",
        timestamp: "2024-01-01T00:01:00Z",
        result: { image_path: "/images/first.png" },
      });
      // Set prompt for second job
      useGenerationStore.getState().setPrompt("Second prompt");
      useGenerationStore.getState().startConnecting("job-2");
      useGenerationStore.getState().addEvent({
        event: "completed",
        job_id: "job-2",
        timestamp: "2024-01-01T00:02:00Z",
        result: { image_path: "/images/second.png" },
      });
      const state = useGenerationStore.getState();
      expect(state.sessionHistory).toHaveLength(2);
      expect(state.sessionHistory[0].imagePath).toBe("/api/images/job-2");
      expect(state.sessionHistory[1].imagePath).toBe("/api/images/job-1");
    });
  });
});
