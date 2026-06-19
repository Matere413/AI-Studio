import type { GenerationState } from "../api/types";
import styles from "./WorkspaceCanvas.module.css";

interface WorkspaceCanvasProps {
  state: GenerationState;
  progress?: number | null;
  imageUrl?: string | null;
  prompt?: string;
  errorMessage?: string | null;
}

function statusLabel(state: GenerationState) {
  if (state === "booting") return "Booting server";
  if (state === "downloadingWeights") return "Downloading weights";
  if (state === "generating") return "Generating";
  if (state === "done") return "Generation complete";
  if (state === "error") return "Generation failed";
  return "Awaiting generation";
}

export function WorkspaceCanvas({
  state,
  progress = null,
  imageUrl = null,
  prompt = "Generated image",
  errorMessage = null,
}: WorkspaceCanvasProps) {
  const currentProgress = progress ?? (state === "done" ? 100 : 0);
  const isActive = state === "booting" || state === "downloadingWeights" || state === "generating";

  return (
    <main aria-label="Studio Workspace" className={styles.workspace}>
      <header className={styles.header}>
        <h2 className={styles.title}>I-Studio Workspace</h2>
        <div className={`text-mono text-caps ${styles.statusText}`} role="status">
          {statusLabel(state)}
        </div>
        <div
          aria-label="Generation progress"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={currentProgress}
          className={styles.progressTrack}
          role="progressbar"
        >
          <div className={styles.progressFill} style={{ width: `${currentProgress}%` }} />
        </div>
      </header>

      <section className={styles.canvas}>
        {state === "error" ? (
          <p className={styles.error} role="alert">
            {errorMessage ?? "Generation failed"}
          </p>
        ) : (
          <div className={styles.artboard}>
            {imageUrl ? (
              <img alt={prompt} className={styles.resultImage} src={imageUrl} />
            ) : (
              <p className={styles.placeholder}>
                {isActive ? "Rendering output..." : "No output yet"}
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
