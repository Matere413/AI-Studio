"use client";

import { useGenerationStore } from "../stores/generationStore";
import AgentAvatar from "@/shared/components/ui/AgentAvatar";
import InputBar from "./InputBar";
import styles from "./GenerationStudio.module.css";

export default function ChatSidebar() {
  const sessionHistory = useGenerationStore((state) => state.sessionHistory);

  return (
    <aside className={styles.panel} aria-label="Agent chat" role="complementary">
      <header className={styles.panelHeader}>
        <AgentAvatar />
        <div>
          <p className={styles.panelEyebrow}>Agent chat</p>
          <h2 className={styles.panelTitle}>Agent chat</h2>
        </div>
      </header>

      <ul className={styles.messageList} aria-label="Conversation">
        {sessionHistory.length === 0 ? (
          <li className={styles.messageBubble}>Start with a prompt, I will keep the workflow aligned.</li>
        ) : (
          sessionHistory.map((item) => (
            <li key={item.id} className={styles.messageBubble}>
              <strong>{item.prompt}</strong>
              <span>{item.completedAt}</span>
            </li>
          ))
        )}
      </ul>

      <InputBar />
    </aside>
  );
}
