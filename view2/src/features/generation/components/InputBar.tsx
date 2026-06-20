"use client";

import { useGenerationStore } from "../stores/generationStore";
import { useGenerationFlow } from "../hooks/useGenerationFlow";
import IconButton from "@/shared/components/ui/IconButton";
import styles from "./GenerationStudio.module.css";
import WorkflowSelector from "./WorkflowSelector";
import SpeedSelector from "./SpeedSelector";

export default function InputBar() {
  const prompt = useGenerationStore((state) => state.prompt);
  const setPrompt = useGenerationStore((state) => state.setPrompt);
  const validationErrors = useGenerationStore((state) => state.validationErrors);
  const { generate, isRunning } = useGenerationFlow();
  const canSubmit = prompt.trim().length > 0 && !validationErrors.prompt && !isRunning;

  return (
    <form
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) {
          void generate();
        }
      }}
    >
      <label className={styles.promptLabel} htmlFor="view2-prompt">
        Prompt
      </label>
      <textarea
        id="view2-prompt"
        className={styles.promptField}
        aria-label="Prompt"
        placeholder="Describe the shot"
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (canSubmit) {
              void generate();
            }
          }
        }}
      />

      <div className={styles.rail}>
        <WorkflowSelector />
        <SpeedSelector />
        <IconButton aria-label="Send prompt" disabled={!canSubmit}>
          ↗
        </IconButton>
      </div>
    </form>
  );
}
