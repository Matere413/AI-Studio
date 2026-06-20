import { useCallback } from "react";
import { AttachIcon, IconButton, PillSelect, SendIcon } from "@/shared/presentation";

export function ChatComposer() {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        // No-op: facade only—no real send (message list remains unchanged)
      }
      // Shift+Enter: default inserts newline, no action needed
    },
    [],
  );

  const handleSend = useCallback(() => {
    // No-op: facade only—no real send
  }, []);

  const handleAttach = useCallback(() => {
    // No-op: facade only—no file dialog
  }, []);

  return (
    <footer className="border-t border-border bg-surface p-4">
      <div className="overflow-hidden rounded-[24px] border border-border bg-base p-2">
        <div className="flex items-start gap-2">
          <IconButton aria-label="Attach File" onClick={handleAttach}>
            <AttachIcon size={18} />
          </IconButton>
          <textarea
            className="min-h-[40px] w-full resize-none border-0 bg-transparent py-[10px] text-[13px] text-primary outline-none"
            aria-label="Message Agent"
            rows={1}
            defaultValue="Make it a bit darker."
            onKeyDown={handleKeyDown}
          />
          <button
            className="ring-offset-base mt-1 flex size-8 flex-shrink-0 items-center justify-center rounded-full bg-accent text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2"
            aria-label="Send Message"
            onClick={handleSend}
          >
            <SendIcon size={16} />
          </button>
        </div>
        <div className="flex gap-2 px-2 pb-1 pt-0.5">
          <PillSelect aria-label="Generation Speed">
            <option>Speed: Fast</option>
            <option>High Quality</option>
          </PillSelect>
          <PillSelect aria-label="Aspect Ratio">
            <option>1:1</option>
            <option>16:9</option>
          </PillSelect>
        </div>
      </div>
    </footer>
  );
}
