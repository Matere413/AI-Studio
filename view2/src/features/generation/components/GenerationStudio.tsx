"use client";

import { useCallback, useMemo, useState } from "react";
import { getImageUrl } from "../api/client";
import type { WorkflowName } from "../api/types";
import { useGenerationFlow } from "../hooks/useGenerationFlow";
import { useUiStore } from "../stores/uiStore";
import { AssetsDrawer, type AssetItem } from "./AssetsDrawer";
import { ChatSidebar, type ChatMessage } from "./ChatSidebar";
import { WorkspaceCanvas } from "./WorkspaceCanvas";
import styles from "./GenerationStudio.module.css";

export function GenerationStudio() {
  const flow = useGenerationFlow();
  const assetsOpen = useUiStore((s) => s.assetsDrawerOpen);
  const toggleAssets = useUiStore((s) => s.toggleAssetsDrawer);

  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "agent-ready",
      role: "agent",
      content: "Describe the image and select a workflow to begin.",
      timestamp: "Ready",
    },
  ]);

  const activePrompt = useMemo(
    () => flow.prompt || "Generated image",
    [flow.prompt],
  );

  // Derive the latest result image from session history
  const latestImageUrl = useMemo(() => {
    if (flow.generationState === "done" && flow.sessionHistory.length > 0) {
      return flow.sessionHistory[0].imagePath;
    }
    return null;
  }, [flow.generationState, flow.sessionHistory]);

  // Derive progress from currentJob
  const currentProgress = useMemo(() => {
    return flow.currentJob?.progress ?? null;
  }, [flow.currentJob]);

  const handleWorkflowChange = useCallback(
    (workflow: WorkflowName) => {
      flow.setParameters({ workflow_name: workflow });
    },
    [flow.setParameters],
  );

  const handleUseTurboChange = useCallback(
    (useTurbo: boolean) => {
      flow.setParameters({ use_turbo: useTurbo });
    },
    [flow.setParameters],
  );

  const handleSubmit = useCallback(() => {
    const trimmed = flow.prompt.trim();
    if (!trimmed || flow.hasErrors) return;

    setMessages((current) => [
      ...current,
      {
        id: `user-${current.length + 1}`,
        role: "user",
        content: trimmed,
        timestamp: "Now",
      },
    ]);

    flow.generate();
  }, [flow.prompt, flow.generate, flow.hasErrors]);

  const handleAssetReady = useCallback(
    (dataUrl: string, file: File) => {
      flow.setReferenceFaceUrl(dataUrl);
      flow.addToGallery(dataUrl);
      setAssets((current) => [
        { id: `${file.name}-${current.length}`, name: file.name, url: dataUrl },
        ...current,
      ]);
    },
    [flow.setReferenceFaceUrl, flow.addToGallery],
  );

  const handleRemoveAsset = useCallback(
    (id: string) => {
      setAssets((current) => {
        const next = current.filter((asset) => asset.id !== id);
        if (next.length === 0) {
          flow.clearReferenceFace();
        }
        return next;
      });
    },
    [flow.clearReferenceFace],
  );

  const selectedWorkflow = flow.parameters.workflow_name ?? "flux2_txt2img";

  return (
    <div className={styles.studio} data-testid="generation-studio">
      <ChatSidebar
        isRunning={flow.isRunning}
        messages={messages}
        onPromptChange={flow.setPrompt}
        onSubmit={handleSubmit}
        onUseTurboChange={handleUseTurboChange}
        onWorkflowChange={handleWorkflowChange}
        prompt={flow.prompt}
        useTurbo={flow.parameters.use_turbo ?? true}
        validationError={
          flow.validationErrors.prompt ??
          flow.validationErrors.referenceImage ??
          flow.validationErrors.parameters
        }
        workflow={selectedWorkflow}
      />
      <div className={styles.workspacePane}>
        <WorkspaceCanvas
          errorMessage={flow.errorMessage}
          imageUrl={latestImageUrl}
          progress={currentProgress}
          prompt={activePrompt}
          state={flow.generationState}
        />
        <AssetsDrawer
          assets={assets}
          onAssetReady={handleAssetReady}
          onRemove={handleRemoveAsset}
          onToggle={toggleAssets}
          open={assetsOpen}
        />
      </div>
    </div>
  );
}
