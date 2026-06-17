"use client";

import PromptPanel from "./PromptPanel";
import IdentitySettingsPanel from "./IdentitySettingsPanel";
import OutputCanvas from "./OutputCanvas";
import EventTerminal from "./EventTerminal";
import SessionHistory from "./SessionHistory";
import { useGenerationFlow } from "../hooks/useGenerationFlow";
import styles from "./GenerationStudio.module.css";

export default function GenerationStudio() {
  const generationFlow = useGenerationFlow();

  return (
    <div className={styles.studio}>
      <aside className={styles.sidebar}>
        <PromptPanel flow={generationFlow} />
        <IdentitySettingsPanel flow={generationFlow} />
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
