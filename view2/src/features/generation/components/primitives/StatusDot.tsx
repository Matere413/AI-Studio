"use client";

import styles from "./StatusDot.module.css";

export type StatusDotTone = "amber" | "green" | "red";

interface StatusDotProps {
  status: StatusDotTone;
  className?: string;
}

export function StatusDot({ status, className }: StatusDotProps) {
  return (
    <span
      aria-hidden="true"
      className={[styles.dot, "status-dot", `status-dot--${status}`, className]
        .filter(Boolean)
        .join(" ")}
    />
  );
}
