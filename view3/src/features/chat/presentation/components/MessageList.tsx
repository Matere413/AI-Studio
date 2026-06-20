import { AvatarMark, ImageIcon } from "@/shared/presentation";
import type { MockMessage } from "@/shared/presentation";

interface MessageListProps {
  messages: MockMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <section className="scrollbar-thin flex-1 overflow-auto p-4" aria-label="Messages">
      {messages.map((msg, i) => (
        <article
          key={i}
          className={`mb-6 flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
        >
          {/* meta line */}
          <div className="mb-1 flex items-center gap-2 text-[11px] tracking-ui text-muted">
            {msg.role === "agent" && <AvatarMark size="sm" />}
            <span>
              {msg.role === "user" ? "You" : "Agent"} &bull;{" "}
              <time dateTime={msg.time}>{msg.time}</time>
            </span>
          </div>

          {msg.card ? (
            /* result card (agent only) */
            <div className="flex min-w-[190px] items-center gap-2 rounded-xl border border-border bg-base p-2">
              <div className="grid size-10 place-items-center rounded-[8px] bg-surface text-muted">
                <ImageIcon size={16} />
              </div>
              <div>
                <div className="text-[12px] font-medium text-primary">{msg.card.title}</div>
                <div className="text-[10px] tracking-ui text-muted">{msg.card.subtitle}</div>
              </div>
            </div>
          ) : (
            /* text bubble */
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
    </section>
  );
}
