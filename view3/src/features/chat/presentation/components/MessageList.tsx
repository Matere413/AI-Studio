"use client";

import { AvatarMark, ImageIcon } from "@/shared/presentation";
import type { ChatMessage } from "@/features/chat/domain/chat-message";

interface MessageListProps {
  messages: ChatMessage[];
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <section className="scrollbar-thin flex-1 overflow-auto p-4" aria-label="Messages">
      {messages.map((msg) => (
        <article
          key={msg.id}
          className={`mb-6 flex flex-col ${
            msg.role === "user" ? "items-end" : "items-start"
          }`}
        >
          {/* meta line */}
          <div className="mb-1 flex items-center gap-2 text-[11px] tracking-ui text-muted">
            {msg.role === "agent" && <AvatarMark size="sm" />}
            <span>
              {msg.role === "user" ? "You" : "Agent"} &bull;{" "}
              <time dateTime={msg.timestamp}>{formatTimestamp(msg.timestamp)}</time>
            </span>
          </div>

          {/* Progress / Event indicator */}
          {msg.type === "progress" || msg.type === "event" ? (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-base px-3 py-2 text-[12px] text-muted">
              {msg.type === "progress" ? (
                <span className="text-accent">{msg.text}</span>
              ) : (
                <span>{msg.text}</span>
              )}
            </div>
          ) : msg.type === "result" ? (
            /* Result card */
            <div className="flex min-w-[190px] items-center gap-2 rounded-xl border border-border bg-base p-2">
              <div className="grid size-10 place-items-center rounded-[8px] bg-surface text-muted">
                <ImageIcon size={16} />
              </div>
              <div>
                <div className="text-[12px] font-medium text-primary">
                  Rendered Output
                </div>
                <div className="text-[10px] tracking-ui text-muted">
                  {msg.imageUrl ? "Loaded in Studio Canvas" : msg.text}
                </div>
              </div>
            </div>
          ) : msg.type === "error" ? (
            /* Error card */
            <div className="flex min-w-[190px] items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-2">
              <div className="grid size-10 place-items-center rounded-[8px] bg-red-100 text-red-600">
                <ImageIcon size={16} />
              </div>
              <div>
                <div className="text-[12px] font-medium text-red-700">
                  Generation Error
                </div>
                <div className="text-[10px] tracking-ui text-red-500">
                  {msg.error?.detail ?? msg.text}
                </div>
              </div>
            </div>
          ) : (
            /* Text bubble (user + agent text messages) */
            <div
              className={
                msg.role === "user"
                  ? "max-w-[95%] rounded-[16px_16px_0_16px] border border-border bg-base px-4 py-2 text-[13px] tracking-[0.01em] text-primary"
                  : "max-w-[95%] text-[13px] tracking-[0.01em] text-primary"
              }
            >
              {msg.text}
            </div>
          )}
        </article>
      ))}

      {messages.length === 0 && (
        <div className="flex h-full items-center justify-center text-[13px] text-muted">
          Send a message to get started.
        </div>
      )}
    </section>
  );
}
