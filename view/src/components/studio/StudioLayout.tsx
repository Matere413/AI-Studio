"use client";

import Sidebar from "./Sidebar";
import Canvas from "./Canvas";
import TerminalLog from "./TerminalLog";
import ImageGallery from "./ImageGallery";
import styles from "./StudioLayout.module.css";

export default function StudioLayout() {
  return (
    <div className={styles.studio}>
      <aside className={styles.sidebar}>
        <Sidebar />
      </aside>
      <main className={styles.canvas}>
        <Canvas />
        <ImageGallery />
      </main>
      <div className={styles.terminal}>
        <TerminalLog />
      </div>
    </div>
  );
}