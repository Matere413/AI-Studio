// ─── Unit Tests: Studio Reducer ─────────────────────────────────
// Tests the page-level state reducer that manages workflow selection,
// job lifecycle, message accumulation, error state, generation state,
// and editing reference — covering the full spec store contract.

import { describe, it } from "node:test";
import assert from "node:assert";
import type { ChatMessage } from "../../features/chat/domain/chat-message.ts";
import { studioReducer, initialStudioState } from "../studio-state.ts";
import type { Asset, StudioState } from "../studio-state.ts";

void describe("studioReducer", () => {
  // ── Initial State ──────────────────────────────────────────

  void it("initializes with flux2_txt2img workflow and no job", () => {
    assert.strictEqual(initialStudioState.selectedWorkflow, "flux2_txt2img");
    assert.strictEqual(initialStudioState.currentJob, null);
    assert.strictEqual(initialStudioState.generationState, "connecting");
    assert.deepStrictEqual(initialStudioState.sessionHistory, []);
    assert.strictEqual(initialStudioState.error, null);
    assert.strictEqual(initialStudioState.referenceFaceUrl, null);
    assert.strictEqual(initialStudioState.editingReferenceBase64, null);
    assert.deepStrictEqual(initialStudioState.sessionAssets, []);
    assert.strictEqual(initialStudioState.useTurbo, false);
  });

  // ── SET_WORKFLOW ──────────────────────────────────────────

  void it("SET_WORKFLOW updates the selected workflow", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_WORKFLOW",
      workflow: "flux2_editing",
    });
    assert.strictEqual(result.selectedWorkflow, "flux2_editing");
    assert.strictEqual(result.currentJob, null);
    assert.strictEqual(result.error, null);
  });

  void it("SET_WORKFLOW clears referenceFaceUrl when switching away from identidad_gguf", () => {
    const state: StudioState = {
      ...initialStudioState,
      selectedWorkflow: "identidad_gguf",
      referenceFaceUrl: "https://example.com/face.png",
    };
    const result = studioReducer(state, {
      type: "SET_WORKFLOW",
      workflow: "flux2_txt2img",
    });
    assert.strictEqual(result.selectedWorkflow, "flux2_txt2img");
    assert.strictEqual(result.referenceFaceUrl, null);
  });

  void it("SET_WORKFLOW clears editingReferenceBase64 when switching away from flux2_editing", () => {
    const state: StudioState = {
      ...initialStudioState,
      selectedWorkflow: "flux2_editing",
      editingReferenceBase64: "iVBORw0KGgoAAAANSUhEUg...",
    };
    const result = studioReducer(state, {
      type: "SET_WORKFLOW",
      workflow: "flux2_txt2img",
    });
    assert.strictEqual(result.selectedWorkflow, "flux2_txt2img");
    assert.strictEqual(result.editingReferenceBase64, null);
  });

  void it("SET_WORKFLOW preserves referenceFaceUrl when switching TO identidad_gguf", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_WORKFLOW",
      workflow: "identidad_gguf",
    });
    assert.strictEqual(result.selectedWorkflow, "identidad_gguf");
    // referenceFaceUrl remains null (no previous value to preserve)
    assert.strictEqual(result.referenceFaceUrl, null);
  });

  void it("SET_WORKFLOW preserves sessionHistory and error", () => {
    const state: StudioState = {
      ...initialStudioState,
      error: "something went wrong",
    };
    const result = studioReducer(state, {
      type: "SET_WORKFLOW",
      workflow: "identidad_gguf",
    });
    assert.strictEqual(result.error, "something went wrong");
    assert.deepStrictEqual(result.sessionHistory, []);
  });

  // ── SET_REFERENCE_FACE_URL ────────────────────────────────

  void it("SET_REFERENCE_FACE_URL sets the URL", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_REFERENCE_FACE_URL",
      url: "https://example.com/face.png",
    });
    assert.strictEqual(result.referenceFaceUrl, "https://example.com/face.png");
  });

  void it("SET_REFERENCE_FACE_URL clears the URL when set to null", () => {
    const state: StudioState = {
      ...initialStudioState,
      referenceFaceUrl: "https://example.com/face.png",
    };
    const result = studioReducer(state, {
      type: "SET_REFERENCE_FACE_URL",
      url: null,
    });
    assert.strictEqual(result.referenceFaceUrl, null);
  });

  // ── START_JOB ────────────────────────────────────────────

  void it("START_JOB sets the currentJob", () => {
    const result = studioReducer(initialStudioState, {
      type: "START_JOB",
      jobId: "job-abc-123",
    });
    assert.strictEqual(result.currentJob, "job-abc-123");
  });

  void it("START_JOB preserves sessionHistory and workflow", () => {
    const state: StudioState = {
      ...initialStudioState,
      selectedWorkflow: "flux2_editing",
    };
    const result = studioReducer(state, {
      type: "START_JOB",
      jobId: "job-xyz",
    });
    assert.strictEqual(result.currentJob, "job-xyz");
    assert.strictEqual(result.selectedWorkflow, "flux2_editing");
    assert.strictEqual(result.error, null);
  });

  void it("START_JOB clears any previous error", () => {
    const state: StudioState = {
      ...initialStudioState,
      error: "previous error",
      currentJob: "old-job",
    };
    const result = studioReducer(state, {
      type: "START_JOB",
      jobId: "new-job",
    });
    assert.strictEqual(result.currentJob, "new-job");
    assert.strictEqual(result.error, null);
  });

  // ── ADD_MESSAGE ───────────────────────────────────────────

  void it("ADD_MESSAGE appends a message to sessionHistory", () => {
    const msg: ChatMessage = {
      id: "msg-1",
      role: "user",
      text: "Hello",
      timestamp: "2026-01-01T00:00:00Z",
      type: "text",
    };
    const result = studioReducer(initialStudioState, {
      type: "ADD_MESSAGE",
      message: msg,
    });
    assert.strictEqual(result.sessionHistory.length, 1);
    assert.strictEqual(result.sessionHistory[0].text, "Hello");
    assert.strictEqual(result.sessionHistory[0].role, "user");
  });

  void it("ADD_MESSAGE accumulates multiple messages in sessionHistory", () => {
    const msg1: ChatMessage = {
      id: "msg-1", role: "user", text: "First",
      timestamp: "2026-01-01T00:00:00Z", type: "text",
    };
    const msg2: ChatMessage = {
      id: "msg-2", role: "agent", text: "Response",
      timestamp: "2026-01-01T00:00:01Z", type: "text",
    };
    const s1 = studioReducer(initialStudioState, { type: "ADD_MESSAGE", message: msg1 });
    const s2 = studioReducer(s1, { type: "ADD_MESSAGE", message: msg2 });
    assert.strictEqual(s2.sessionHistory.length, 2);
    assert.strictEqual(s2.sessionHistory[0].text, "First");
    assert.strictEqual(s2.sessionHistory[1].text, "Response");
  });

  void it("ADD_MESSAGE preserves other state fields", () => {
    const state: StudioState = {
      ...initialStudioState,
      currentJob: "job-1",
      selectedWorkflow: "identidad_gguf",
    };
    const msg: ChatMessage = {
      id: "msg-1", role: "agent", text: "Hello agent!",
      timestamp: "2026-01-01T00:00:00Z", type: "event",
    };
    const result = studioReducer(state, { type: "ADD_MESSAGE", message: msg });
    assert.strictEqual(result.currentJob, "job-1");
    assert.strictEqual(result.selectedWorkflow, "identidad_gguf");
    assert.strictEqual(result.sessionHistory.length, 1);
  });

  // ── SET_ERROR ─────────────────────────────────────────────

  void it("SET_ERROR sets the error string", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_ERROR",
      error: "GPU out of memory",
    });
    assert.strictEqual(result.error, "GPU out of memory");
  });

  void it("SET_ERROR with null clears the error", () => {
    const state: StudioState = {
      ...initialStudioState,
      error: "previous error",
    };
    const result = studioReducer(state, {
      type: "SET_ERROR",
      error: null,
    });
    assert.strictEqual(result.error, null);
  });

  // ── CLEAR_JOB ─────────────────────────────────────────────

  void it("CLEAR_JOB resets currentJob to null and clears error", () => {
    const state: StudioState = {
      ...initialStudioState,
      currentJob: "job-123",
      error: "something broke",
    };
    const result = studioReducer(state, { type: "CLEAR_JOB" });
    assert.strictEqual(result.currentJob, null);
    assert.strictEqual(result.error, null);
    // sessionHistory and workflow preserved
    assert.deepStrictEqual(result.sessionHistory, []);
    assert.strictEqual(result.selectedWorkflow, "flux2_txt2img");
  });

  // ── SET_GENERATION_STATE ──────────────────────────────────

  void it("SET_GENERATION_STATE updates generationState", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_GENERATION_STATE",
      state: "streaming",
    });
    assert.strictEqual(result.generationState, "streaming");
  });

  void it("SET_GENERATION_STATE can transition to completed", () => {
    const state: StudioState = {
      ...initialStudioState,
      generationState: "streaming",
    };
    const result = studioReducer(state, {
      type: "SET_GENERATION_STATE",
      state: "completed",
    });
    assert.strictEqual(result.generationState, "completed");
  });

  void it("SET_GENERATION_STATE can transition to exhausted", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_GENERATION_STATE",
      state: "exhausted",
    });
    assert.strictEqual(result.generationState, "exhausted");
  });

  // ── SET_EDITING_REFERENCE ─────────────────────────────────

  void it("SET_EDITING_REFERENCE sets the base64 string", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_EDITING_REFERENCE",
      base64: "iVBORw0KGgoAAAANSUhEUg...",
    });
    assert.strictEqual(
      result.editingReferenceBase64,
      "iVBORw0KGgoAAAANSUhEUg...",
    );
  });

  void it("SET_EDITING_REFERENCE clears when set to null", () => {
    const state: StudioState = {
      ...initialStudioState,
      editingReferenceBase64: "iVBORw0KGgoAAAANSUhEUg...",
    };
    const result = studioReducer(state, {
      type: "SET_EDITING_REFERENCE",
      base64: null,
    });
    assert.strictEqual(result.editingReferenceBase64, null);
  });

  // ── SET_USE_TURBO ──────────────────────────────────────────

  void it("SET_USE_TURBO sets useTurbo to true", () => {
    const result = studioReducer(initialStudioState, {
      type: "SET_USE_TURBO",
      value: true,
    });
    assert.strictEqual(result.useTurbo, true);
  });

  void it("SET_USE_TURBO sets useTurbo to false", () => {
    const state: StudioState = {
      ...initialStudioState,
      useTurbo: true,
    };
    const result = studioReducer(state, {
      type: "SET_USE_TURBO",
      value: false,
    });
    assert.strictEqual(result.useTurbo, false);
  });

  // ── ADD_SESSION_ASSET ──────────────────────────────────────

  void it("ADD_SESSION_ASSET appends an asset to sessionAssets", () => {
    const asset = {
      id: "asset-1",
      name: "test.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const result = studioReducer(initialStudioState, {
      type: "ADD_SESSION_ASSET",
      asset,
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].name, "test.png");
  });

  void it("ADD_SESSION_ASSET accumulates multiple assets", () => {
    const asset1 = {
      id: "a1", name: "a.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const asset2 = {
      id: "a2", name: "b.pdf",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "file" as const,
      addedAt: "2026-01-01T00:00:01Z",
    };
    const s1 = studioReducer(initialStudioState, {
      type: "ADD_SESSION_ASSET",
      asset: asset1,
    });
    const s2 = studioReducer(s1, {
      type: "ADD_SESSION_ASSET",
      asset: asset2,
    });
    assert.strictEqual(s2.sessionAssets.length, 2);
    assert.strictEqual(s2.sessionAssets[0].name, "a.png");
    assert.strictEqual(s2.sessionAssets[1].name, "b.pdf");
  });

  void it("ADD_SESSION_ASSET preserves other state fields", () => {
    const asset = {
      id: "a1", name: "c.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      currentJob: "job-1",
      useTurbo: true,
    };
    const result = studioReducer(state, {
      type: "ADD_SESSION_ASSET",
      asset,
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.currentJob, "job-1");
    assert.strictEqual(result.useTurbo, true);
  });

  void it("ADD_SESSION_ASSET caps at 10 assets (discards oldest)", () => {
    const MAX = 10;
    const initialAssets: Asset[] = Array.from({ length: MAX }, (_, i) => ({
      id: `asset-${i + 1}`,
      name: `file-${i + 1}.png`,
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: new Date(Date.UTC(2026, 0, i + 1)).toISOString(),
    }));
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: initialAssets,
    };
    const newAsset: Asset = {
      id: "asset-11",
      name: "new-file.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: new Date(Date.UTC(2026, 0, 11)).toISOString(),
    };
    const result = studioReducer(state, { type: "ADD_SESSION_ASSET", asset: newAsset });
    assert.strictEqual(result.sessionAssets.length, MAX);
    // The oldest (asset-1) should be dropped, asset-2 moves to front
    assert.strictEqual(result.sessionAssets[0].id, "asset-2");
    // The newest (asset-11) should be at the end
    assert.strictEqual(result.sessionAssets[result.sessionAssets.length - 1].id, "asset-11");
  });

  // ── REMOVE_SESSION_ASSET ───────────────────────────────────

  void it("REMOVE_SESSION_ASSET removes an asset by id", () => {
    const asset1 = {
      id: "a1", name: "keep.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const asset2 = {
      id: "a2", name: "remove.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:01Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset1, asset2],
    };
    const result = studioReducer(state, {
      type: "REMOVE_SESSION_ASSET",
      id: "a2",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].id, "a1");
  });

  void it("REMOVE_SESSION_ASSET does nothing when id not found", () => {
    const asset = {
      id: "a1", name: "only.png",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "image" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "REMOVE_SESSION_ASSET",
      id: "nonexistent",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].id, "a1");
  });

  void it("REMOVE_SESSION_ASSET preserves other state fields", () => {
    const asset = {
      id: "a1", name: "doc.pdf",
      r2Url: "",
      uploadStatus: "idle" as const,
      type: "file" as const,
      addedAt: "2026-01-01T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
      useTurbo: true,
      currentJob: "job-99",
    };
    const result = studioReducer(state, {
      type: "REMOVE_SESSION_ASSET",
      id: "a1",
    });
    assert.strictEqual(result.sessionAssets.length, 0);
    assert.strictEqual(result.useTurbo, true);
    assert.strictEqual(result.currentJob, "job-99");
  });

  // ── SET_WORKFLOW resets useTurbo for identidad_gguf ────────

  void it("SET_WORKFLOW resets useTurbo to false when switching to identidad_gguf", () => {
    const state: StudioState = {
      ...initialStudioState,
      useTurbo: true,
    };
    const result = studioReducer(state, {
      type: "SET_WORKFLOW",
      workflow: "identidad_gguf",
    });
    assert.strictEqual(result.useTurbo, false);
  });

  void it("SET_WORKFLOW preserves useTurbo when switching between Flux workflows", () => {
    const state: StudioState = {
      ...initialStudioState,
      selectedWorkflow: "flux2_txt2img",
      useTurbo: true,
    };
    const result = studioReducer(state, {
      type: "SET_WORKFLOW",
      workflow: "flux2_editing",
    });
    assert.strictEqual(result.useTurbo, true);
  });

  // ── Unknown action ─────────────────────────────────────────

  void it("unknown action returns state unchanged", () => {
    const result = studioReducer(initialStudioState, { type: "UNKNOWN" } as never);
    assert.strictEqual(result, initialStudioState);
  });
});
