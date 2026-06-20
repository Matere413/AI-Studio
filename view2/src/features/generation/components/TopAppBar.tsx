"use client";

import styles from "./GenerationStudio.module.css";

const ACTIONS = ["Export", "Publish", "Search", "Fullscreen"] as const;

export default function TopAppBar() {
  return (
    <header className={styles.topAppBar} aria-label="Studio top bar" role="toolbar">
      <div>
        <p className={styles.topAppBarEyebrow}>Center column</p>
        <h1 className={styles.topAppBarTitle}>Generative AI Studio</h1>
      </div>

      <div className={styles.topAppBarActions}>
        {ACTIONS.map((action) => (
          <button
            aria-disabled="true"
            className={styles.topAppBarAction}
            disabled
            key={action}
            tabIndex={-1}
            type="button"
          >
            {action}
          </button>
        ))}
      </div>
    </header>
  );
}
