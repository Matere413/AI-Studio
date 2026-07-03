"use client";

import { useCallback } from "react";
import { ChatSidebar } from "./ChatSidebar";
import type { ChatMessage } from "../../domain/chat-message";
import type { ChatManualControls } from "./ChatComposer";
import type { OrchestrateStage } from "../../domain/dto";

/**
 * Minimal session asset shape that ChatPanel receives from the page.
 * Matches the fields from StudioState.sessionAssets that handleSend needs.
 */
export interface ChatPanelSessionAsset {
  id: string;
  name?: string;
  type: string;
  uploadStatus: string;
}

export interface ChatPanelProps {
  messages: ChatMessage[];
  onSubmit: (
    prompt: string,
    sessionAssets: ChatPanelSessionAsset[],
    selectedAssetIds: string[],
  ) => boolean | Promise<boolean>;
  disabled: boolean;
  manualControls: ChatManualControls;
  sessionAssets: ChatPanelSessionAsset[];
  selectedAssetIds: string[];
  orchestrationStages: OrchestrateStage[];
}

/**
 * Thin boundary component that wraps ChatSidebar with the exact
 * selectedAssets mapping that HomePage currently does inline.
 *
 * Extracted so the data flow (sessionAssets + selectedAssetIds →
 * selectedAssets display + onSend wiring) can be tested at the
 * component level with react-test-renderer.
 *
 * HomePage MUST use this component — the test proves the wiring works.
 */
export function ChatPanel({
  messages,
  onSubmit,
  disabled,
  manualControls,
  sessionAssets,
  selectedAssetIds,
  orchestrationStages,
}: ChatPanelProps) {
  // Build the selectedAssetSet from the current props (not from closure).
  // This is the same Set-based filter that page.tsx currently uses inline.
  const selectedAssetSet = new Set(selectedAssetIds);

  // onSend passes the CURRENT props through to onSubmit explicitly.
  // This prevents stale closures: the props are read at render time,
  // not captured in a closure at creation time.
  const onSend = useCallback(
    (prompt: string) => onSubmit(prompt, sessionAssets, selectedAssetIds),
    [onSubmit, sessionAssets, selectedAssetIds],
  );

  return (
    <ChatSidebar
      messages={messages}
      submitState={{ onSend, disabled }}
      manualControls={manualControls}
      selectedAssets={{
        assets: sessionAssets
          .filter((asset) => selectedAssetSet.has(asset.id))
          .map((asset) => ({
            id: asset.id,
            name: asset.name ?? asset.id,
            uploadStatus: asset.uploadStatus,
          })),
      }}
      orchestrationState={{ stages: orchestrationStages }}
    />
  );
}
