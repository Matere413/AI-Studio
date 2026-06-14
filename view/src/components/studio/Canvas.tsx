"use client";

import Image from "next/image";
import { useGenerationStore } from "@/stores/generationStore";
import PixelProgressBar from "./PixelProgressBar";
import styles from "./Canvas.module.css";

export default function Canvas() {
  const currentJob = useGenerationStore((s) => s.currentJob);
  const generationState = useGenerationStore((s) => s.generationState);
  const errorMessage = useGenerationStore((s) => s.errorMessage);
  const latestResult = useGenerationStore(
    (s) => s.sessionHistory[0] ?? null
  );

  return (
    <div className={styles.canvas}>
      {generationState === "idle" && !currentJob && !latestResult && (
        <div className={styles.placeholder}>
          <span className={styles.placeholderIcon}>◈</span>
          <p className={styles.placeholderText}>
            Enter a prompt and click Generate to start
          </p>
        </div>
      )}

      {currentJob && (
        <div className={styles.output}>
          <div className={styles.statusRow}>
            <span className={styles.statusBadge} data-state={generationState}>
              {generationState === "connecting" && "Connecting..."}
              {generationState === "generating" && "Generating"}
              {generationState === "done" && "Complete"}
              {generationState === "error" && "Error"}
            </span>
            {currentJob.progress !== null && (
              <span className={styles.progressText}>
                {Math.round(currentJob.progress * 100)}%
              </span>
            )}
          </div>

          {(generationState === "connecting" || generationState === "generating") && (
            <PixelProgressBar
              progress={currentJob.progress}
              isColdStart={generationState === "connecting" || currentJob.progress === null}
            />
          )}
        </div>
      )}

      {latestResult && generationState === "done" && (
        <div className={styles.output}>
          <div className={styles.statusRow}>
            <span className={styles.statusBadge} data-state="done">
              Complete
            </span>
          </div>
          <div className={styles.imageContainer}>
            <Image
              src={latestResult.imagePath}
              alt={latestResult.prompt}
              fill
              className={styles.outputImage}
              style={{ objectFit: "contain" }}
            />
          </div>
        </div>
      )}

      {generationState === "error" && errorMessage && (
        <div className={styles.errorBanner}>
          <span className={styles.errorIcon}>⚠</span>
          <p>{errorMessage}</p>
        </div>
      )}
    </div>
  );
}