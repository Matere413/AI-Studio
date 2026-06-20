"use client";

import Image from "next/image";
import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

const MAX_VISIBLE_PROMPT_LENGTH = 80;

function truncatePrompt(prompt: string) {
  return prompt.length > MAX_VISIBLE_PROMPT_LENGTH ? `${prompt.slice(0, MAX_VISIBLE_PROMPT_LENGTH)}…` : prompt;
}

export default function SessionHistory() {
  const sessionHistory = useGenerationStore((state) => state.sessionHistory);

  return (
    <section className={styles.historySection} aria-label="Session history">
      <p className={styles.historyTitle}>Session history</p>
      {sessionHistory.length === 0 ? (
        <p className={styles.historyEmpty}>No completed sessions yet</p>
      ) : (
        <ul className={styles.historyGrid} aria-label="Completed generations" role="list">
          {sessionHistory.map((item) => (
            <li className={styles.historyItem} key={item.id}>
              <Image
                className={styles.historyImage}
                src={item.imagePath}
                alt={`Generated image for ${item.prompt}`}
                width={240}
                height={180}
              />
              <p className={styles.historyPrompt} title={item.prompt}>
                {truncatePrompt(item.prompt)}
              </p>
              <time className={styles.historyTimestamp} dateTime={item.completedAt}>
                {item.completedAt}
              </time>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
