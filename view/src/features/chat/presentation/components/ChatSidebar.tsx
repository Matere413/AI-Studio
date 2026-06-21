"use client";

import { AvatarMark, IconButton, SettingsIcon } from "@/shared/presentation";
import type { ChatMessage } from "@/features/chat/domain/chat-message";
import type { WorkflowName } from "@/features/chat/domain/dto";
import { MessageList } from "./MessageList";
import { ChatComposer } from "./ChatComposer";

interface ChatSidebarProps {
  messages: ChatMessage[];
  workflow: WorkflowName;
  onWorkflowChange: (workflow: WorkflowName) => void;
  onSend: (prompt: string) => void;
  referenceFaceUrl: string | null;
  onReferenceFaceUrlChange: (url: string | null) => void;
  editingReferenceBase64: string | null;
  onEditingReferenceChange: (base64: string | null) => void;
  useTurbo: boolean;
  onTurboChange: (useTurbo: boolean) => void;
  disabled?: boolean;
}

export function ChatSidebar({
  messages,
  workflow,
  onWorkflowChange,
  onSend,
  referenceFaceUrl,
  onReferenceFaceUrlChange,
  editingReferenceBase64,
  onEditingReferenceChange,
  useTurbo,
  onTurboChange,
  disabled = false,
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
        onSend={onSend}
        workflow={workflow}
        onWorkflowChange={onWorkflowChange}
        referenceFaceUrl={referenceFaceUrl}
        onReferenceFaceUrlChange={onReferenceFaceUrlChange}
        editingReferenceBase64={editingReferenceBase64}
        onEditingReferenceChange={onEditingReferenceChange}
        useTurbo={useTurbo}
        onTurboChange={onTurboChange}
        disabled={disabled}
      />
    </aside>
  );
}
