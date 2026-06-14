"use client";

import styles from "./PixelProgressBar.module.css";

interface PixelProgressBarProps {
  /** 0 to 1 progress, or null for indeterminate (cold start) */
  progress: number | null;
  /** Whether we're in cold-start state (no numeric progress yet) */
  isColdStart: boolean;
}

export default function PixelProgressBar({
  progress,
  isColdStart,
}: PixelProgressBarProps) {
  if (isColdStart || progress === null) {
    return (
      <div className={styles.bar}>
        <div className={styles.indeterminate} />
      </div>
    );
  }

  const percent = Math.round(Math.max(0, Math.min(1, progress)) * 100);

  return (
    <div className={styles.bar}>
      <div
        className={styles.fill}
        style={{ width: `${percent}%` }}
      />
      <span className={styles.label}>{percent}%</span>
    </div>
  );
}