"use client";

import type { WorkflowName } from "../api/types";
import { InputBar } from "./InputBar";
import { GenerationControls } from "./GenerationControls";
import { WorkflowSelector } from "./WorkflowSelector";
import { AgentAvatar } from "./primitives/AgentAvatar";
import styles from "./ChatSidebar.module.css";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp?: string;
}

interface ChatSidebarProps {
  prompt: string;
  workflow: WorkflowName;
  useTurbo?: boolean;
  messages: ChatMessage[];
  onPromptChange: (value: string) => void;
  onWorkflowChange: (value: WorkflowName) => void;
  onUseTurboChange?: (value: boolean) => void;
  onSubmit: () => void;
  isRunning?: boolean;
  validationError?: string;
}

export function ChatSidebar({
  prompt,
  workflow,
  useTurbo = true,
  messages,
  onPromptChange,
  onWorkflowChange,
  onUseTurboChange,
  onSubmit,
      isRunning = false,
      validationError,
    }: ChatSidebarProps) {
  return (
    <aside aria-label="Agent Chat" className={`surface-panel ${styles.sidebar}`}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <AgentAvatar className={styles.avatar} name="Orchestrator" />
          <div>
            <h1 className={styles.title}>Agent Chat</h1>
            <p className={`text-mono text-caps ${styles.subtitle}`}>Orchestrator</p>
          </div>
        </div>
        <button aria-label="Chat settings" className="btn btn-ghost" type="button">
          Settings
        </button>
      </header>

      <div className={styles.messages}>
        {messages.length === 0 ? (
          <p className={styles.empty}>Start with a prompt to brief the generation agent.</p>
        ) : (
          messages.map((message) => (
            <article
              className={`${styles.message} ${
                message.role === "user" ? styles.userMessage : styles.agentMessage
              }`}
              key={message.id}
            >
              <span className={`text-mono text-caps ${styles.messageMeta}`}>
                {message.role} {message.timestamp ? `· ${message.timestamp}` : ""}
              </span>
              <p className={styles.messageText}>{message.content}</p>
            </article>
          ))
        )}
      </div>

      <div className={styles.controls}>
        <WorkflowSelector
          disabled={isRunning}
          onChange={onWorkflowChange}
          value={workflow}
        />
      </div>
      <div className={styles.composer}>
        <InputBar
          disabled={isRunning}
          onChange={onPromptChange}
          onSubmit={onSubmit}
          validationError={validationError}
          value={prompt}
        />
        <GenerationControls
          disabled={isRunning}
          onUseTurboChange={onUseTurboChange ?? (() => {})}
          useTurbo={useTurbo}
          workflow={workflow}
        />
      </div>
    </aside>
  );
}
