"use client";

import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

const EMPTY_EVENTS = [] as const;

export default function EventTerminal() {
  const currentEvents = useGenerationStore((state) => state.currentJob?.events);
  const terminalEvent = useGenerationStore((state) => state.terminalEvent);
  const events = currentEvents ?? (terminalEvent ? [terminalEvent] : EMPTY_EVENTS);

  const formatEventLabel = (event: { event: string; message?: string | null }) => {
    if (event.message) return event.message;
    if (event.event === "booting_server") return "Booting server";
    if (event.event === "downloading_weights") return "Downloading weights";
    if (event.event === "generating") return "Generating";
    if (event.event === "completed") return "Completed";
    if (event.event === "error") return "Error";
    return event.event;
  };

  return (
    <section className={styles.eventTerminal} aria-label="Event terminal">
      <p className={styles.eventTerminalTitle}>Event terminal</p>
      <ul
        className={styles.eventLog}
        aria-label="Generation events"
        role="log"
      >
        {events.length === 0 ? (
          <li className={styles.eventLine}>Waiting for generation events</li>
        ) : (
          events.map((event) => (
            <li key={`${event.job_id}-${event.event}-${event.timestamp}`} className={styles.eventLine}>
              <span className={styles.eventName}>{event.event}</span>
              <span>{formatEventLabel(event)}</span>
              {"progress" in event && typeof event.progress === "number" ? (
                <span>{`${Math.round(event.progress)}%`}</span>
              ) : null}
            </li>
          ))
        )}
      </ul>
    </section>
  );
}
