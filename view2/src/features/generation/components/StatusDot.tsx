"use client";

import type { GenerationState } from "../api/types";
import styles from "./GenerationStudio.module.css";

const STATUS_TONES: Record<GenerationState, string> = {
  idle: "var(--fg-muted)",
  booting: "var(--wheat-400)",
  downloadingWeights: "var(--wheat-300)",
  generating: "var(--accent)",
  done: "var(--success)",
  error: "var(--danger)",
};

const STATUS_LABELS: Record<GenerationState, string> = {
  idle: "Idle",
  booting: "Booting",
  downloadingWeights: "Downloading weights",
  generating: "Generating",
  done: "Complete",
  error: "Error",
};

export default function StatusDot({
  progress,
  state,
}: {
  progress?: number | null;
  state: GenerationState;
}) {
  const hasProgress = typeof progress === "number";
  const pulsing = state === "booting" || state === "downloadingWeights" || state === "generating";
  const toneLabel = hasProgress ? `${STATUS_LABELS[state]} ${Math.round(progress)}%` : STATUS_LABELS[state];

  return (
    <div className={styles.statusDot} aria-label="Generation status" aria-live="polite" role="status">
      <span
        aria-label="Status tone"
        className={styles.statusTone}
        data-pulsing={pulsing ? "true" : "false"}
        style={{ backgroundColor: STATUS_TONES[state] }}
      />
      <span>{toneLabel}</span>
    </div>
  );
}
