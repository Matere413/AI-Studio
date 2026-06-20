import { AvatarMark, IconButton, SettingsIcon } from "@/shared/presentation";
import type { MockMessage } from "@/shared/presentation";
import { MessageList } from "./MessageList";
import { ChatComposer } from "./ChatComposer";

interface ChatSidebarProps {
  messages: MockMessage[];
}

export function ChatSidebar({ messages }: ChatSidebarProps) {
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
      <ChatComposer />
    </aside>
  );
}
