"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ChatPanel } from "@/features/chat/presentation/components/ChatPanel";
import { StudioTopBar } from "@/features/studio/presentation/components/StudioTopBar";
import { StudioCanvas } from "@/features/studio/presentation/components/StudioCanvas";
import { AssetsDrawer } from "@/features/assets/presentation/components/AssetsDrawer";

import {
  studioReducer,
  initialStudioState,
} from "../studio-state";
import type { ChatPanelSessionAsset } from "@/features/chat/presentation/components/ChatPanel";
import {
  useGenerationJob,
  submitOrchestrateRequest,
  jobEventsToChatMessages,
} from "@/features/chat/application";
import { submitOrchestrate } from "@/shared/infrastructure/api-client";
import { createProject } from "@/features/assets/infrastructure/api";
import { executeUpload } from "@/features/assets/application/use-upload.ts";
import type { ChatMessage } from "@/features/chat/domain/chat-message";
import { createOrchestrateStages, type OrchestrateResponse, type OrchestrateStage } from "../../features/chat/domain/dto";
import { getSafeOrchestrationMessage } from "@/features/chat/presentation/components/orchestration-ui";
import { useAuth } from "@/features/auth/application/use-auth";

const BREAKPOINT_LG = 1024;

let nextMessageId = 1;

function createUserMessage(text: string): ChatMessage {
  return {
    id: `user-${nextMessageId++}`,
    role: "user",
    text,
    timestamp: new Date().toISOString(),
    type: "text",
  };
}

export default function StudioPage() {
  const { isAuthenticated, isVerified } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const userToggled = useRef(false);

  /** The active project for asset uploads. Null until user explicitly creates one. */
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);

  /** Reference file selected via ChatComposer, before upload completes. */
  const [editingReferenceFile, setEditingReferenceFile] = useState<File | null>(null);
  /** Whether the editing reference file is currently being uploaded. */
  const [isReferenceUploading, setIsReferenceUploading] = useState(false);
  const [orchestrationStages, setOrchestrationStages] = useState<OrchestrateStage[]>([]);
  const [isOrchestrationPending, setIsOrchestrationPending] = useState(false);

  const [state, dispatch] = useReducer(studioReducer, initialStudioState);
  const {
    selectedWorkflow,
    currentJob,
    sessionHistory,
    error,
    referenceFaceUrl,
    sessionAssets,
    selectedAssetIds,
    useTurbo,
  } = state;

  // Track which events we've already converted to messages
  const lastEventCountRef = useRef(0);
  // Guard against double submission
  const isSubmittingRef = useRef(false);

  // WebSocket hook — connects when we have a job ID
  const genJob = useGenerationJob(currentJob);

  // Sync new WS events to the message list
  useEffect(() => {
    if (genJob.events.length > lastEventCountRef.current) {
      const newEvents = genJob.events.slice(lastEventCountRef.current);
      const newMessages = jobEventsToChatMessages(newEvents);
      for (const msg of newMessages) {
        dispatch({ type: "ADD_MESSAGE", message: msg });
      }
      lastEventCountRef.current = genJob.events.length;
    }
  }, [genJob.events]);

  // Sync generation state to the reducer store contract
  useEffect(() => {
    dispatch({ type: "SET_GENERATION_STATE", state: genJob.state });
  }, [genJob.state]);

  // When generation completes, make the image URL available to canvas
  const imageUrl =
    genJob.state === "completed" && currentJob
      ? `/api/images/${currentJob}`
      : null;

  const handleBlockedOrchestration = useCallback((response: OrchestrateResponse) => {
    const text = getSafeOrchestrationMessage(response);
    const type = response.outcome === "error" ? "error" : "event";
    dispatch({
      type: "ADD_MESSAGE",
      message: {
        id: `${response.outcome}-${nextMessageId++}`,
        role: "agent",
        text,
        timestamp: new Date().toISOString(),
        type,
        ...(response.outcome === "error"
          ? { error: { code: response.error_code ?? "orchestration_error", detail: text } }
          : {}),
      },
    });
    if (response.outcome === "error") {
      dispatch({ type: "SET_ERROR", error: text });
    }
  }, []);

  // Handle sending a prompt — receives assets and ids from ChatPanel directly,
  // eliminating stale closure risk: the data flows as arguments, not captured
  // reference. The seam `submitOrchestrateRequest` is tested in
  // `build-generate-request.test.ts` under "submitOrchestrateRequest — full
  // page-level request submission path".
  const handleSend = useCallback(
    async (prompt: string, assets: ChatPanelSessionAsset[], ids: string[]) => {
      if (!prompt.trim()) return false;
      if (isSubmittingRef.current) return false;
      isSubmittingRef.current = true;
      setIsOrchestrationPending(true);
      try {
        // Add user message immediately
        dispatch({ type: "ADD_MESSAGE", message: createUserMessage(prompt.trim()) });

        setOrchestrationStages(createOrchestrateStages({ planning: "running" }));

        const response = await submitOrchestrateRequest(
          prompt.trim(),
          assets,
          ids,
          { projectId, workflowHint: selectedWorkflow, useTurbo },
          submitOrchestrate,
        );
        setOrchestrationStages(response.stages);

        if (response.outcome !== "job_started") {
          handleBlockedOrchestration(response);
          return response.outcome !== "error";
        }

        // Start the job — this triggers useGenerationJob
        dispatch({ type: "START_JOB", jobId: response.job_id ?? "" });
        lastEventCountRef.current = 0; // Reset event tracking for new job
        return true;
      } finally {
        isSubmittingRef.current = false;
        setIsOrchestrationPending(false);
      }
    },
    [projectId, handleBlockedOrchestration, selectedWorkflow, useTurbo],
  );

  const handleWorkflowChange = useCallback(
    (workflow: typeof selectedWorkflow) => {
      dispatch({ type: "SET_WORKFLOW", workflow });
    },
    [],
  );

  const handleReferenceFaceUrlChange = useCallback(
    (url: string | null) => {
      dispatch({ type: "SET_REFERENCE_FACE_URL", url });
    },
    [],
  );

  const handleTurboChange = useCallback(
    (useTurbo: boolean) => {
      dispatch({ type: "SET_USE_TURBO", value: useTurbo });
    },
    [],
  );

  const handleRemoveAsset = useCallback(
    (id: string) => {
      dispatch({ type: "REMOVE_SESSION_ASSET", id });
    },
    [],
  );

  // Handle creating a project (enables asset uploads). Auth gating:
  //   anonymous → redirect to /login?next=<current path>
  //   authenticated but unverified → do NOT call /projects (backend 403 anyway;
  //     the EmailVerificationBanner shown in the top bar guides the user)
  //   authenticated + verified → POST /projects succeeds
  const handleCreateProject = useCallback(async (name: string) => {
    if (!isAuthenticated) {
      const next = typeof window !== "undefined" ? window.location.pathname : "/";
      window.location.href = `/login?next=${encodeURIComponent(next)}`;
      return;
    }
    if (!isVerified) {
      setProjectError("Verify your email to save projects.");
      return;
    }
    setIsCreatingProject(true);
    setProjectError(null);
    try {
      const project = await createProject(name);
      setProjectId(project.id);
    } catch (err) {
      const msg =
        err instanceof Error && "detail" in err
          ? (err as { detail: string }).detail
          : err instanceof Error
            ? err.message
            : "Failed to create project. Please try again.";
      setProjectError(msg);
    } finally {
      setIsCreatingProject(false);
    }
  }, [isAuthenticated, isVerified]);

  // Handle reference file selection in ChatComposer — replaced the old
  // FileReader/readAsDataURL path with the R2 upload pipeline (Chat Base64 Hole fix).
  const handleEditingReferenceFileChange = useCallback(
    async (file: File | null) => {
      setEditingReferenceFile(file);
      if (!file || !projectId) return;

      setIsReferenceUploading(true);
      const assetId = crypto.randomUUID();

      // Add asset to session immediately with idle status
      dispatch({
        type: "ADD_SESSION_ASSET",
        asset: {
          id: assetId,
          name: file.name,
          r2Url: "",
          type: "image",
          uploadStatus: "idle",
          addedAt: new Date().toISOString(),
        },
      });

      try {
        const { r2Url, serverAssetId } = await executeUpload(
          assetId,
          file.name,
          file,
          projectId,
          (status) => dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId, status }),
        );
        // Update the asset with server-assigned ID and R2 URL for thumbnail rendering
        dispatch({ type: "UPDATE_ASSET_SERVER_ID", oldId: assetId, newId: serverAssetId, r2Url });
      } catch {
        dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId, status: "error" });
      } finally {
        setIsReferenceUploading(false);
      }
    },
    [projectId, dispatch],
  );

  /* Responsive drawer: collapsed on small viewports, open on >=1024px */
  useEffect(() => {
    let prevWidth = window.innerWidth;

    function handleResize() {
      const currentWidth = window.innerWidth;
      const crossedUp = prevWidth < BREAKPOINT_LG && currentWidth >= BREAKPOINT_LG;
      const crossedDown = prevWidth >= BREAKPOINT_LG && currentWidth < BREAKPOINT_LG;

      if (!userToggled.current) {
        if (crossedUp) setDrawerOpen(true);
        if (crossedDown) setDrawerOpen(false);
      }
      prevWidth = currentWidth;
    }

    if (window.innerWidth >= BREAKPOINT_LG) {
      setDrawerOpen(true);
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const toggleDrawer = useCallback(() => {
    userToggled.current = true;
    setDrawerOpen((prev) => !prev);
  }, []);

  const isGenerating =
    currentJob !== null &&
    (genJob.state === "connecting" || genJob.state === "streaming");

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-base">
      <ChatPanel
        messages={sessionHistory}
        onSubmit={handleSend}
        disabled={isGenerating || isOrchestrationPending}
        manualControls={{
          workflow: selectedWorkflow,
          onWorkflowChange: handleWorkflowChange,
          referenceFaceUrl,
          onReferenceFaceUrlChange: handleReferenceFaceUrlChange,
          editingReferenceFile,
          onEditingReferenceFileChange: handleEditingReferenceFileChange,
          isEditingReferenceUploading: isReferenceUploading,
          useTurbo,
          onTurboChange: handleTurboChange,
        }}
        sessionAssets={sessionAssets}
        selectedAssetIds={selectedAssetIds}
        orchestrationStages={orchestrationStages}
      />

      <main className="flex min-w-0 flex-1 flex-col bg-base">
        <StudioTopBar
          onToggleAssets={toggleDrawer}
          assetsExpanded={drawerOpen}
        />

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <StudioCanvas
            jobId={currentJob}
            generationState={genJob.state}
            progress={genJob.progress}
            imageUrl={imageUrl}
            error={error}
            retry={genJob.retry}
          />
          <AssetsDrawer
            assets={sessionAssets}
            isOpen={drawerOpen}
            dispatch={dispatch}
            onRemoveAsset={handleRemoveAsset}
            projectId={projectId}
            onCreateProject={handleCreateProject}
            isCreatingProject={isCreatingProject}
            projectError={projectError}
            onDismissProjectError={() => setProjectError(null)}
            selectedAssetIds={selectedAssetIds}
            onToggleSelectedAsset={(id) => dispatch({ type: "TOGGLE_SELECTED_ASSET", id })}
          />
        </div>
      </main>
    </div>
  );
}
