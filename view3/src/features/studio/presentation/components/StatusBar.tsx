import type { ConnectionState } from "@/features/chat/application";

export interface StatusBarProps {
  status?: ConnectionState;
  progress?: number;
  /** Return null when no active job exists. */
  hasJob?: boolean;
}

const STATUS_LABELS: Record<ConnectionState, string> = {
  connecting: "CONNECTING...",
  streaming: "STREAMING...",
  completed: "COMPLETED",
  error: "ERROR",
  exhausted: "CONNECTION LOST",
};

export function StatusBar({ status, progress, hasJob }: StatusBarProps) {
  if (!hasJob) return null;

  if (!status) {
    return (
      <div
        className="absolute right-6 top-6 flex items-center gap-2 font-mono text-[11px] leading-none tracking-caps text-muted"
        role="status"
        aria-live="polite"
      >
        <span className="size-2 rounded-full bg-muted" />
        IDLE
      </div>
    );
  }

  const isActive = status === "connecting" || status === "streaming";
  const isError = status === "error" || status === "exhausted";

  return (
    <div
      className="absolute right-6 top-6 flex items-center gap-2 font-mono text-[11px] leading-none tracking-caps"
      role="status"
      aria-live="polite"
      data-status={status}
    >
      <span
        className={`size-2 rounded-full ${
          isError
            ? "bg-red-500"
            : isActive
              ? "pulse-status bg-accent"
              : "bg-green-500"
        }`}
      />
      <span className={isError ? "text-red-500" : "text-accent"}>
        {STATUS_LABELS[status]}
      </span>
      {isActive && progress !== undefined && (
        <span className="text-muted">({progress}%)</span>
      )}
    </div>
  );
}
