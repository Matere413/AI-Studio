"use client";

import Image from "next/image";
import { useState } from "react";
import { useGenerationStore } from "../stores/generationStore";
import PixelProgressBar from "@/shared/components/ui/PixelProgressBar";
import styles from "./OutputCanvas.module.css";

function GeneratedPreview({
  imagePath,
  prompt,
}: {
  imagePath: string;
  prompt: string;
}) {
  const [previewStatus, setPreviewStatus] = useState<"loading" | "ready" | "error">("loading");

  return (
    <div className={styles.imageContainer}>
      {previewStatus !== "ready" && (
        <div className={styles.previewState} data-state={previewStatus} aria-live="polite">
          {previewStatus === "error" ? "Preview failed to load" : "Loading preview..."}
        </div>
      )}
      <Image
        src={imagePath}
        alt={`Generated image for ${prompt}`}
        fill
        className={styles.outputImage}
        style={{ objectFit: "contain" }}
        onLoad={() => setPreviewStatus("ready")}
        onError={() => setPreviewStatus("error")}
      />
    </div>
  );
}

export default function OutputCanvas() {
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
          <GeneratedPreview
            key={latestResult.id}
            imagePath={latestResult.imagePath}
            prompt={latestResult.prompt}
          />
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
