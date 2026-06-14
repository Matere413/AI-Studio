"use client";

import Image from "next/image";
import { useGenerationStore } from "@/stores/generationStore";
import styles from "./ImageGallery.module.css";

export const MAX_PROMPT_LENGTH = 80;

export function truncatePrompt(prompt: string): string {
  if (prompt.length <= MAX_PROMPT_LENGTH) return prompt;
  return prompt.slice(0, MAX_PROMPT_LENGTH) + "...";
}

export default function ImageGallery() {
  const sessionHistory = useGenerationStore((s) => s.sessionHistory);

  if (sessionHistory.length === 0) {
    return (
      <div className={styles.gallery}>
        <p className={styles.emptyState}>No generations yet</p>
      </div>
    );
  }

  return (
    <div className={styles.gallery}>
      <h3 className={styles.galleryTitle}>Session History</h3>
      <div className={styles.grid}>
        {sessionHistory.map((item) => (
          <div key={item.id} className={styles.card}>
            <div className={styles.thumbnailWrap}>
              <Image
                src={item.imagePath}
                alt={item.prompt}
                fill
                className={styles.thumbnail}
                style={{ objectFit: "cover" }}
              />
            </div>
            <div className={styles.cardBody}>
              <p className={styles.cardPrompt}>{truncatePrompt(item.prompt)}</p>
              <span className={styles.cardMeta}>
                {item.parameters.workflow_name ?? "unknown"} ·{" "}
                {new Date(item.completedAt).toLocaleTimeString()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}