"use client";

import { AvatarMark, IconButton, SettingsIcon } from "@/shared/presentation";
import type { ChatMessage } from "@/features/chat/domain/chat-message";
import { MessageList } from "./MessageList";
import { ChatComposer, type ChatManualControls, type ChatOrchestrationState, type ChatSelectedAssetsState, type ChatSubmitState } from "./ChatComposer";

interface ChatSidebarProps {
  messages: ChatMessage[];
  submitState: ChatSubmitState;
  manualControls: ChatManualControls;
  selectedAssets?: ChatSelectedAssetsState;
  orchestrationState?: ChatOrchestrationState;
}

export function ChatSidebar({
  messages,
  submitState,
  manualControls,
  selectedAssets,
  orchestrationState,
}: ChatSidebarProps) {
  return (
    <aside
      className="flex w-[300px] flex-shrink-0 flex-col border-r border-border bg-surface"
      aria-label="Agent Chat"
    >
      {/* sidebar topbar */}
      <header className="flex h-12 flex-shrink-0 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <AvatarMark size="md" />
          <h1 className="text-sm font-medium text-primary">Agent Chat</h1>
        </div>
        <IconButton aria-label="Chat Settings">
          <SettingsIcon size={18} />
        </IconButton>
      </header>

      <MessageList messages={messages} />
      <ChatComposer
        submitState={submitState}
        manualControls={manualControls}
        selectedAssets={selectedAssets}
        orchestrationState={orchestrationState}
      />
    </aside>
  );
}
