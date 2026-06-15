"use client";

import PromptPanel from "./PromptPanel";
import OutputCanvas from "./OutputCanvas";
import EventTerminal from "./EventTerminal";
import SessionHistory from "./SessionHistory";
import styles from "./GenerationStudio.module.css";

export default function GenerationStudio() {
  return (
    <div className={styles.studio}>
      <aside className={styles.sidebar}>
        <PromptPanel />
      </aside>
      <main className={styles.canvas}>
        <OutputCanvas />
        <SessionHistory />
      </main>
      <div className={styles.terminal}>
        <EventTerminal />
      </div>
    </div>
  );
}
