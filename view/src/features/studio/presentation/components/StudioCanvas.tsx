"use client";

import { useMemo } from "react";
import Image from "next/image";
import { IconButton, ImageIcon, SearchIcon, FitToScreenIcon } from "@/shared/presentation";
import type { ConnectionState } from "@/features/chat/application";
import { StatusBar } from "./StatusBar";

interface StudioCanvasProps {
  jobId: string | null;
  generationState: ConnectionState | null;
  progress: number;
  /** Proxy image URL to display when generation completes. */
  imageUrl: string | null;
  /** Error message to display when generation fails. */
  error: string | null;
  /** Retry connection callback for exhausted WS state. */
  retry?: () => void;
}

const STATE_LABELS: Record<string, string> = {
  connecting: "CONNECTING",
  streaming: "GENERATING",
  completed: "COMPLETED",
  error: "ERROR",
  exhausted: "ERROR",
};

function describeState(state: string | null): string {
  return state ? STATE_LABELS[state] ?? "" : "";
}

function DotGrid() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      <defs>
        <pattern id="dot-grid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
          <circle cx="10" cy="10" r="0.75" className="fill-border" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dot-grid)" />
    </svg>
  );
}

export function StudioCanvas({
  jobId,
  generationState,
  progress,
  imageUrl,
  error,
  retry,
}: StudioCanvasProps) {
  const hasOutput = imageUrl !== null;
  const isGenerating =
    generationState === "connecting" || generationState === "streaming";
  const isExhausted = generationState === "exhausted";

  const metaLabel = useMemo(() => {
    const label = imageUrl
      ? imageUrl.split("/").pop() ?? "output.png"
      : `job_${jobId}`;
    const format = label.includes(".") ? ` (${label.split(".").pop()})` : "";
    const status = describeState(generationState);
    return `${label}${format} — ${status}${progress > 0 ? ` (${progress}%)` : ""}`;
  }, [imageUrl, jobId, generationState, progress]);

  // When there's no active job, render only the dot-grid background
  if (!jobId) {
    return (
      <section
        role="tabpanel"
        id="panel-studio-canvas"
        aria-labelledby="tab-studio-canvas"
        className="flex min-w-0 flex-1 flex-col"
      >
        <header className="flex h-[53px] flex-shrink-0 items-center justify-between border-b border-border px-4">
          <span className="font-mono text-[11px] leading-[1.4] text-muted">
            No active job
          </span>
          <div className="flex gap-2" />
        </header>
        <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-base">
          <DotGrid />
        </div>
      </section>
    );
  }

  return (
    <section
      role="tabpanel"
      id="panel-studio-canvas"
      aria-labelledby="tab-studio-canvas"
      className="flex min-w-0 flex-1 flex-col"
    >
      {/* canvas meta bar */}
      <header className="flex h-[53px] flex-shrink-0 items-center justify-between border-b border-border px-4">
        <span className="font-mono text-[11px] leading-[1.4] text-muted">
          {metaLabel}
        </span>
        <div className="flex gap-2">
          <IconButton aria-label="Zoom Out">
            <SearchIcon size={14} />
          </IconButton>
          <IconButton aria-label="Fit to Screen">
            <FitToScreenIcon size={14} />
          </IconButton>
        </div>
      </header>

      {/* canvas stage */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-base">
        <DotGrid />

        <StatusBar status={generationState ?? undefined} progress={progress} hasJob={true} />

        {/* Output area */}
        {hasOutput ? (
          <div className="relative flex aspect-square w-[min(400px,62vw)] items-center justify-center overflow-hidden border border-border bg-base">
            <Image
              src={imageUrl!}
              alt="Generated output"
              fill
              className="object-contain"
              sizes="(max-width: 400px) 100vw, 400px"
              priority
              unoptimized
            />
            {/* accent border overlay */}
            <div className="pointer-events-none absolute inset-0 border-b border-accent" />
          </div>
        ) : isExhausted ? (
          /* Retry connection state */
          <div className="relative flex aspect-square w-[min(400px,62vw)] items-center justify-center overflow-hidden border border-red-200 bg-red-50">
            <div className="z-[1] flex flex-col items-center gap-3 text-red-500">
              <ImageIcon size={24} />
              <span className="text-[13px] text-center px-4">
                Connection lost after multiple attempts
              </span>
              {retry && (
                <button
                  onClick={retry}
                  className="mt-1 rounded-md bg-red-500 px-4 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
                >
                  Retry Connection
                </button>
              )}
            </div>
          </div>
        ) : error ? (
          /* Error state */
          <div className="relative flex aspect-square w-[min(400px,62vw)] items-center justify-center overflow-hidden border border-red-200 bg-red-50">
            <div className="z-[1] flex flex-col items-center gap-3 text-red-500">
              <ImageIcon size={24} />
              <span className="text-[13px] text-center px-4">{error}</span>
            </div>
          </div>
        ) : (
          /* Idle / waiting */
          <div className="relative flex aspect-square w-[min(400px,62vw)] items-center justify-center overflow-hidden border border-border bg-base">
            <div className="pointer-events-none absolute inset-0 border-b border-accent" />
            <div className="z-[1] flex flex-col items-center gap-3 text-muted">
              <ImageIcon size={24} />
              <span className="text-[13px]">
                {isGenerating ? STATE_LABELS.streaming : "Send a prompt to generate"}
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
