// ─── Studio Page State ─────────────────────────────────────────
// useReducer state, actions, and reducer for the main studio page.
// Manages workflow selection, job lifecycle, message accumulation,
// and error state — lean enough to live alongside the page.

import type { WorkflowName } from "../features/chat/domain/dto.ts";
import type { ChatMessage } from "../features/chat/domain/chat-message.ts";
import type { ConnectionState } from "../features/chat/application/use-generation-job.ts";

// ─── Asset (session-local) ─────────────────────────────────────

export type UploadStatus =
  | "idle"
  | "compressing"
  | "requesting_ticket"
  | "uploading"
  | "finalizing"
  | "done"
  | "error";

export interface Asset {
  id: string;
  name: string;
  /** R2 presigned URL for display (replaces deprecated dataUrl). */
  r2Url: string;
  type: "image" | "file";
  /** Current upload lifecycle status. */
  uploadStatus: UploadStatus;
  /** ISO 8601 timestamp. */
  addedAt: string;
}

// ─── State ─────────────────────────────────────────────────────

export interface StudioState {
  selectedWorkflow: WorkflowName;
  currentJob: string | null;
  /** Current generation connection state (synced from useGenerationJob). */
  generationState: ConnectionState;
  /** Ordered list of chat messages / job events for the session. */
  sessionHistory: ChatMessage[];
  error: string | null;
  referenceFaceUrl: string | null;
  /** Raw base64-encoded data for flux2_editing reference image. */
  editingReferenceBase64: string | null;
  /** Session-local assets uploaded by the user (Data URIs). */
  sessionAssets: Asset[];
  /** Enable turbo mode for Flux workflows. */
  useTurbo: boolean;
}

// ─── Actions ───────────────────────────────────────────────────

export type StudioAction =
  | { type: "SET_WORKFLOW"; workflow: WorkflowName }
  | { type: "SET_REFERENCE_FACE_URL"; url: string | null }
  | { type: "START_JOB"; jobId: string }
  | { type: "ADD_MESSAGE"; message: ChatMessage }
  | { type: "SET_ERROR"; error: string | null }
  | { type: "CLEAR_JOB" }
  | { type: "SET_GENERATION_STATE"; state: ConnectionState }
  | { type: "SET_EDITING_REFERENCE"; base64: string | null }
  | { type: "SET_USE_TURBO"; value: boolean }
  | { type: "ADD_SESSION_ASSET"; asset: Asset }
  | { type: "REMOVE_SESSION_ASSET"; id: string }
  | {
      type: "SET_ASSET_UPLOAD_STATUS";
      assetId: string;
      status: UploadStatus;
    }
  | {
      type: "UPDATE_ASSET_SERVER_ID";
      oldId: string;
      newId: string;
    };

// ─── Initial State ─────────────────────────────────────────────

export const initialStudioState: StudioState = {
  selectedWorkflow: "flux2_txt2img",
  currentJob: null,
  generationState: "connecting",
  sessionHistory: [],
  error: null,
  referenceFaceUrl: null,
  editingReferenceBase64: null,
  sessionAssets: [],
  useTurbo: false,
};

// ─── Reducer ──────────────────────────────────────────────────

export function studioReducer(
  state: StudioState,
  action: StudioAction,
): StudioState {
  switch (action.type) {
    case "SET_WORKFLOW": {
      // When switching away from identidad_gguf, clear the reference URL
      const clearRef: Partial<StudioState> =
        state.selectedWorkflow === "identidad_gguf"
          ? { referenceFaceUrl: null }
          : {};
      // When switching away from flux2_editing, clear the editing base64
      const clearEdit: Partial<StudioState> =
        state.selectedWorkflow === "flux2_editing"
          ? { editingReferenceBase64: null }
          : {};
      // When switching to identidad_gguf, reset turbo (not supported)
      const resetTurbo: Partial<StudioState> =
        action.workflow === "identidad_gguf"
          ? { useTurbo: false }
          : {};
      return {
        ...state,
        ...clearRef,
        ...clearEdit,
        ...resetTurbo,
        selectedWorkflow: action.workflow,
      };
    }

    case "SET_REFERENCE_FACE_URL":
      return { ...state, referenceFaceUrl: action.url };

    case "START_JOB":
      return { ...state, currentJob: action.jobId, error: null };

    case "ADD_MESSAGE":
      return {
        ...state,
        sessionHistory: [...state.sessionHistory, action.message],
      };

    case "SET_ERROR":
      return { ...state, error: action.error };

    case "CLEAR_JOB":
      return { ...state, currentJob: null, error: null };

    case "SET_GENERATION_STATE":
      return { ...state, generationState: action.state };

    case "SET_EDITING_REFERENCE":
      return { ...state, editingReferenceBase64: action.base64 };

    case "SET_USE_TURBO":
      return { ...state, useTurbo: action.value };

    case "ADD_SESSION_ASSET": {
      const MAX_ASSETS = 10;
      const next = [...state.sessionAssets, action.asset];
      return {
        ...state,
        sessionAssets: next.length > MAX_ASSETS ? next.slice(next.length - MAX_ASSETS) : next,
      };
    }

    case "REMOVE_SESSION_ASSET":
      return {
        ...state,
        sessionAssets: state.sessionAssets.filter((a) => a.id !== action.id),
      };

    case "SET_ASSET_UPLOAD_STATUS":
      return {
        ...state,
        sessionAssets: state.sessionAssets.map((a) =>
          a.id === action.assetId
            ? { ...a, uploadStatus: action.status }
            : a,
        ),
      };

    case "UPDATE_ASSET_SERVER_ID":
      return {
        ...state,
        sessionAssets: state.sessionAssets.map((a) =>
          a.id === action.oldId ? { ...a, id: action.newId } : a,
        ),
      };

    default:
      return state;
  }
}
