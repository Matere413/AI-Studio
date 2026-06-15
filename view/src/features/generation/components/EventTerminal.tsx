"use client";

import { useState } from "react";
import { useGenerationStore, type JobEvent } from "../stores/generationStore";
import styles from "./EventTerminal.module.css";

const EMPTY_EVENTS: JobEvent[] = [];

export default function EventTerminal() {
  const events = useGenerationStore((s) => s.currentJob?.events ?? EMPTY_EVENTS);
  const generationState = useGenerationStore((s) => s.generationState);
  const [collapsed, setCollapsed] = useState(true);

  const coldStartMessage =
    (generationState === "connecting" ||
      (generationState === "generating" && events.length === 0)) &&
    "Starting generation server...";

  return (
    <div className={styles.terminal}>
      <button
        className={styles.terminalBar}
        onClick={() => setCollapsed(!collapsed)}
        type="button"
      >
        <span className={styles.terminalDot} />
        <span className={styles.terminalDot} />
        <span className={styles.terminalDot} />
        <span className={styles.terminalTitle}>Terminal</span>
        <span className={styles.terminalToggle}>
          {collapsed ? "▸" : "▾"}
        </span>
      </button>
      {!collapsed && (
        <div className={`${styles.terminalBody} ${styles.crt}`}>
          {coldStartMessage && (
            <div className={styles.terminalLine}>
              <span className={styles.terminalPrompt}>{">"}</span>{" "}
              {coldStartMessage}
              <span className={styles.cursor} />
            </div>
          )}
          {events.map((event, i) => (
            <div key={i} className={styles.terminalLine}>
              <span className={styles.terminalPrompt}>{">"}</span>{" "}
              <span className={styles.terminalEvent}>
                [{event.event.toUpperCase()}]
              </span>{" "}
              {event.message ?? event.event}{" "}
              {event.progress !== null &&
                event.progress !== undefined &&
                `(${Math.round(event.progress * 100)}%)`}
            </div>
          ))}
          {events.length === 0 && !coldStartMessage && (
            <div className={styles.terminalLine}>
              <span className={styles.terminalPrompt}>{">"}</span> Waiting for
              events...
              <span className={styles.cursor} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
