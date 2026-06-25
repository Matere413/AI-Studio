"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { ChatSidebar } from "@/features/chat/presentation/components/ChatSidebar";
import { StudioTopBar } from "@/features/studio/presentation/components/StudioTopBar";
import { StudioCanvas } from "@/features/studio/presentation/components/StudioCanvas";
import { AssetsDrawer } from "@/features/assets/presentation/components/AssetsDrawer";

import {
  studioReducer,
  initialStudioState,
} from "./studio-state";
import {
  useGenerationJob,
  buildGenerateRequest,
  jobEventsToChatMessages,
} from "@/features/chat/application";
import { submitGenerate, fetchWithSession } from "@/shared/infrastructure/api-client";
import { env } from "@/shared/infrastructure/env";
import type { ChatMessage } from "@/features/chat/domain/chat-message";

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

export default function HomePage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const userToggled = useRef(false);

  /** The active project for asset uploads. Created on mount. */
  const [projectId, setProjectId] = useState<string | null>(null);
  const projectInitRef = useRef(false);

  const [state, dispatch] = useReducer(studioReducer, initialStudioState);
  const {
    selectedWorkflow,
    currentJob,
    sessionHistory,
    error,
    referenceFaceUrl,
    editingReferenceBase64,
    sessionAssets,
    useTurbo,
  } = state;

  // Initialize a default project on mount
  useEffect(() => {
    if (projectInitRef.current) return;
    projectInitRef.current = true;

    (async () => {
      try {
        // Try fetching existing projects first
        const res = await fetchWithSession(`${env.apiBaseUrl}/projects`);
        if (res.ok) {
          const projects: { id: string; name: string }[] = await res.json();
          if (projects.length > 0) {
            setProjectId(projects[0].id);
            return;
          }
        }
        // No projects exist — create a default one
        const createRes = await fetchWithSession(`${env.apiBaseUrl}/projects`, {
          method: "POST",
          body: JSON.stringify({ name: "Default Project" }),
        });
        if (createRes.ok) {
          const project: { id: string; name: string } = await createRes.json();
          setProjectId(project.id);
        }
      } catch {
        // Silently fail — user can still use the app without R2 uploads
        console.warn("Failed to initialize workspace project");
      }
    })();
  }, []);

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

  // Handle sending a prompt
  const handleSend = useCallback(
    async (prompt: string) => {
      if (!prompt.trim()) return;
      if (isSubmittingRef.current) return;
      isSubmittingRef.current = true;
      try {
        // Add user message immediately
        dispatch({ type: "ADD_MESSAGE", message: createUserMessage(prompt.trim()) });

        // Build the request — per-workflow params
        let request: ReturnType<typeof buildGenerateRequest>;
        try {
          const params: Record<string, unknown> = {};
          if (selectedWorkflow === "flux2_editing") {
            params.imageBase64 = editingReferenceBase64 ?? undefined;
          } else if (selectedWorkflow === "identidad_gguf") {
            params.imageUrl = referenceFaceUrl ?? undefined;
          }
          params.useTurbo = useTurbo;
          request = buildGenerateRequest(prompt.trim(), selectedWorkflow, params);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Invalid request";
          dispatch({ type: "SET_ERROR", error: msg });
          dispatch({
            type: "ADD_MESSAGE",
            message: {
              id: `error-${nextMessageId++}`,
              role: "agent",
              text: `Error: ${msg}`,
              timestamp: new Date().toISOString(),
              type: "error",
              error: { code: "invalid_request", detail: msg },
            },
          });
          return;
        }

        // Submit
        const response = await submitGenerate(request);

        if ("code" in response) {
          dispatch({
            type: "SET_ERROR",
            error: response.detail,
          });
          // Also add an error message to the chat
          dispatch({
            type: "ADD_MESSAGE",
            message: {
              id: `error-${nextMessageId++}`,
              role: "agent",
              text: `Error: ${response.detail}`,
              timestamp: new Date().toISOString(),
              type: "error",
              error: { code: response.code, detail: response.detail },
            },
          });
          return;
        }

        // Start the job — this triggers useGenerationJob
        dispatch({ type: "START_JOB", jobId: response.job_id });
        lastEventCountRef.current = 0; // Reset event tracking for new job
      } finally {
        isSubmittingRef.current = false;
      }
    },
    [selectedWorkflow, referenceFaceUrl, editingReferenceBase64, useTurbo],
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
      <ChatSidebar
        messages={sessionHistory}
        workflow={selectedWorkflow}
        onWorkflowChange={handleWorkflowChange}
        onSend={handleSend}
        referenceFaceUrl={referenceFaceUrl}
        onReferenceFaceUrlChange={handleReferenceFaceUrlChange}
        editingReferenceBase64={editingReferenceBase64}
        onEditingReferenceChange={(base64) =>
          dispatch({ type: "SET_EDITING_REFERENCE", base64 })
        }
        useTurbo={useTurbo}
        onTurboChange={handleTurboChange}
        disabled={isGenerating}
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
            projectId={projectId ?? "default"}
          />
        </div>
      </main>
    </div>
  );
}
