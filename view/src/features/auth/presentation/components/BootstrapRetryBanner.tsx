"use client";

interface BootstrapRetryBannerProps {
  shown: boolean;
  onRetry: () => void;
  retrying?: boolean;
  error?: string | null;
}

export function BootstrapRetryBanner({
  shown,
  onRetry,
  retrying = false,
  error = null,
}: BootstrapRetryBannerProps) {
  if (!shown) return null;
  const label = humanizeBootstrapError(error);
  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex items-center gap-2.5 rounded-md border border-highlight/40 bg-highlight/10 px-3 py-1.5 text-[12px] text-highlight"
      data-state="bootstrap_retryable"
      data-retrying={retrying ? "true" : "false"}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="M21 12a9 9 0 1 1-2.64-6.36" />
        <polyline points="21 4 21 9 16 9" />
      </svg>
      <span>
        {retrying ? "Reconnecting…" : `Connection issue${label ? `: ${label}` : ""}.`}
      </span>
      <button
        aria-label="Retry connection"
        onClick={onRetry}
        disabled={retrying}
        className="font-medium underline-offset-2 transition-colors duration-studio ease-studio hover:underline disabled:opacity-50 disabled:no-underline"
      >
        {retrying ? "Retrying" : "Retry"}
      </button>
    </div>
  );
}

function humanizeBootstrapError(code: string | null | undefined): string {
  if (!code) return "";
  switch (code) {
    case "timeout":
      return "request timed out";
    case "client_error":
      return "network unreachable";
    case "rate_limited":
      return "rate limited";
    case "internal_error":
      return "backend error";
    default:
      return "transient backend error";
  }
}
