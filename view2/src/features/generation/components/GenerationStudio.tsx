"use client";

import { useMemo, useState } from "react";
import type { GenerationState, WorkflowName } from "../api/types";
import { AssetsDrawer, type AssetItem } from "./AssetsDrawer";
import { ChatSidebar, type ChatMessage } from "./ChatSidebar";
import { WorkspaceCanvas } from "./WorkspaceCanvas";
import styles from "./GenerationStudio.module.css";

interface GenerationStudioProps {
  state?: GenerationState;
  progress?: number | null;
  imageUrl?: string | null;
  errorMessage?: string | null;
}

export function GenerationStudio({
  state = "idle",
  progress = null,
  imageUrl = null,
  errorMessage = null,
}: GenerationStudioProps) {
  const [prompt, setPrompt] = useState("");
  const [workflow, setWorkflow] = useState<WorkflowName>("flux2_txt2img");
  const [assetsOpen, setAssetsOpen] = useState(false);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: "agent-ready",
      role: "agent",
      content: "Describe the image and select a workflow to begin.",
      timestamp: "Ready",
    },
  ]);

  const isRunning = state === "booting" || state === "downloadingWeights" || state === "generating";
  const activePrompt = useMemo(() => prompt || "Generated image", [prompt]);

  const handleSubmit = () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;

    setMessages((current) => [
      ...current,
      {
        id: `user-${current.length + 1}`,
        role: "user",
        content: trimmed,
        timestamp: "Now",
      },
    ]);
  };

  const handleAssetReady = (dataUrl: string, file: File) => {
    setAssets((current) => [
      { id: `${file.name}-${current.length}`, name: file.name, url: dataUrl },
      ...current,
    ]);
  };

  return (
    <div className={styles.studio} data-testid="generation-studio">
      <ChatSidebar
        isRunning={isRunning}
        messages={messages}
        onPromptChange={setPrompt}
        onSubmit={handleSubmit}
        onWorkflowChange={setWorkflow}
        prompt={prompt}
        workflow={workflow}
      />
      <div className={styles.workspacePane}>
        <WorkspaceCanvas
          errorMessage={errorMessage}
          imageUrl={imageUrl}
          progress={progress}
          prompt={activePrompt}
          state={state}
        />
        <AssetsDrawer
          assets={assets}
          onAssetReady={handleAssetReady}
          onRemove={(id) => setAssets((current) => current.filter((asset) => asset.id !== id))}
          onToggle={() => setAssetsOpen((current) => !current)}
          open={assetsOpen}
        />
      </div>
    </div>
  );
}
