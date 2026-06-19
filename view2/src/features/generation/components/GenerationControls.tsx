"use client";

import type { WorkflowName } from "../api/types";
import { useUiStore } from "../stores/uiStore";
import styles from "./GenerationControls.module.css";

interface GenerationControlsProps {
  workflow?: WorkflowName;
  useTurbo: boolean;
  onUseTurboChange: (value: boolean) => void;
  disabled?: boolean;
}

const ASPECT_OPTIONS = ["1:1", "16:9", "9:16"] as const;

export function GenerationControls({
  workflow,
  useTurbo,
  onUseTurboChange,
  disabled = false,
}: GenerationControlsProps) {
  const aspectRatio = useUiStore((state) => state.aspectRatio);
  const setAspectRatio = useUiStore((state) => state.setAspectRatio);
  const isDisabled = disabled || !workflow;

  return (
    <section aria-label="Generation controls" className={styles.controls} role="group">
      <div className={styles.group}>
        <p className={`text-mono text-caps ${styles.label}`}>Speed</p>
        <div aria-label="Speed" className={styles.toggleGroup} role="group">
          <button
            aria-pressed={useTurbo}
            className={`${styles.toggleButton} ${useTurbo ? styles.toggleButtonActive : ""}`}
            disabled={isDisabled}
            onClick={() => onUseTurboChange(true)}
            type="button"
          >
            Fast
          </button>
          <button
            aria-pressed={!useTurbo}
            className={`${styles.toggleButton} ${!useTurbo ? styles.toggleButtonActive : ""}`}
            disabled={isDisabled}
            onClick={() => onUseTurboChange(false)}
            type="button"
          >
            Quality
          </button>
        </div>
      </div>

      <label className={styles.field}>
        <span className={`text-mono text-caps ${styles.label}`}>Aspect ratio</span>
        <select
          aria-label="Aspect ratio"
          className={`input text-mono ${styles.select}`}
          disabled={isDisabled}
          onChange={(event) => setAspectRatio(event.target.value as (typeof ASPECT_OPTIONS)[number])}
          value={aspectRatio}
        >
          {ASPECT_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}
