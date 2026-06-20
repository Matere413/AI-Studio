"use client";

import Image from "next/image";
import { useGenerationStore } from "../stores/generationStore";
import StatusDot from "./StatusDot";
import styles from "./GenerationStudio.module.css";

export default function OutputCanvas() {
  const prompt = useGenerationStore((state) => state.prompt);
  const generationState = useGenerationStore((state) => state.generationState);
  const currentJob = useGenerationStore((state) => state.currentJob);
  const sessionHistory = useGenerationStore((state) => state.sessionHistory);
  const latestResult = generationState === "done" ? sessionHistory[0] ?? null : null;

  return (
    <section
      className={styles.outputCanvas}
      aria-label="Output canvas"
      data-surface="dotted"
    >
      <article
        className={styles.outputArtboard}
        aria-label="Artboard chrome"
      >
        <header className={styles.outputHeader}>
          <p className={styles.outputCaption}>Prompt caption</p>
          <StatusDot progress={currentJob?.progress ?? null} state={generationState} />
        </header>

        <div className={styles.outputPreview}>
          {latestResult ? (
            <Image
              className={styles.outputImage}
              src={latestResult.imagePath}
              alt={`Generated image for ${latestResult.prompt}`}
              width={960}
              height={720}
            />
          ) : (
            <p className={styles.outputPlaceholder}>Awaiting the first render</p>
          )}
        </div>

        <footer className={styles.outputBottomRail} aria-label="Canvas bottom rail">
          <span className={styles.outputPromptLabel}>Prompt</span>
          <p className={styles.outputPromptValue}>{prompt || "No prompt yet"}</p>
        </footer>
      </article>
    </section>
  );
}
