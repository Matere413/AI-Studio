"use client";

import type { GenerationFlowViewModel } from "../hooks/useGenerationFlow";
import styles from "./PromptPanel.module.css";

const WORKFLOWS = [
  { value: "txt2img" as const, label: "TXT → IMG" },
  { value: "img2img" as const, label: "IMG → IMG" },
  { value: "controlnet" as const, label: "ControlNet" },
  { value: "product_premium" as const, label: "Product" },
];

const PRODUCT_FORMATS = [
  { value: "square" as const, label: "Square" },
  { value: "vertical" as const, label: "Vertical" },
];

interface PromptPanelProps {
  flow: GenerationFlowViewModel;
}

export default function PromptPanel({ flow }: PromptPanelProps) {
  const {
    prompt,
    parameters,
    validationErrors,
    isRunning,
    hasErrors,
    setPrompt,
    setParameters,
    generate,
    cancel,
    reset,
  } = flow;
  const isProductWorkflow = parameters.workflow_name === "product_premium";
  const selectedFormat = parameters.format ?? "square";

  return (
    <div className={styles.sidebar}>
      <header className={styles.header}>
        <span className={styles.eyebrow}>Generative Studio</span>
        <h1 className={styles.title}>Create</h1>
      </header>

      <div className={styles.section}>
        <label className={styles.label} htmlFor="prompt-input">
          Prompt
        </label>
        <textarea
          id="prompt-input"
          className={styles.textarea}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe what you want to generate..."
          disabled={isRunning}
          maxLength={1000}
          rows={5}
        />
        <div className={styles.charCounter}>
          <span>
            {prompt.length}/1000
          </span>
          {validationErrors.prompt && (
            <span className={styles.error}>{validationErrors.prompt}</span>
          )}
        </div>
      </div>

      <div className={styles.section}>
        <label className={styles.label}>Workflow</label>
        <div className={styles.chipGroup}>
          {(isProductWorkflow ? WORKFLOWS.filter((wf) => wf.value === "product_premium") : WORKFLOWS).map((wf) => (
            <button
              key={wf.value}
              className={`${styles.chip} ${
                parameters.workflow_name === wf.value ? styles.chipOn : ""
              }`}
              onClick={() =>
                setParameters(
                  wf.value === "product_premium"
                    ? { workflow_name: wf.value, format: parameters.format ?? "square" }
                    : { workflow_name: wf.value }
                )
              }
              disabled={isRunning}
              type="button"
            >
              {wf.label}
            </button>
          ))}
        </div>
        {validationErrors.parameters && (
          <span className={styles.error}>{validationErrors.parameters}</span>
        )}
      </div>

      {isProductWorkflow ? (
        <div className={styles.section}>
          <label className={styles.label}>Format</label>
          <div className={styles.chipGroup}>
            {PRODUCT_FORMATS.map((format) => (
              <button
                key={format.value}
                className={`${styles.chip} ${
                  selectedFormat === format.value ? styles.chipOn : ""
                }`}
                onClick={() =>
                  setParameters({
                    workflow_name: "product_premium",
                    format: format.value,
                  })
                }
                disabled={isRunning}
                type="button"
              >
                {format.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className={styles.section}>
            <label className={styles.label} htmlFor="checkpoint-input">
              Checkpoint URL <span className={styles.optional}>(optional)</span>
            </label>
            <input
              id="checkpoint-input"
              className={styles.input}
              type="url"
              value={parameters.checkpoint_url ?? ""}
              onChange={(e) => setParameters({ checkpoint_url: e.target.value })}
              placeholder="https://..."
              disabled={isRunning}
            />
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="lora-input">
              LoRA URL <span className={styles.optional}>(optional)</span>
            </label>
            <input
              id="lora-input"
              className={styles.input}
              type="url"
              value={parameters.lora_url ?? ""}
              onChange={(e) => setParameters({ lora_url: e.target.value })}
              placeholder="https://..."
              disabled={isRunning}
            />
          </div>
        </>
      )}

      <div className={styles.actions}>
        {isRunning ? (
          <button
            className={`${styles.btn} ${styles.btnGhost}`}
            onClick={cancel}
            type="button"
          >
            Cancel
          </button>
        ) : (
          <button
            className={`${styles.btn} ${styles.btnPrimary}`}
            onClick={generate}
            disabled={hasErrors || !prompt.trim()}
            type="button"
          >
            Generate
          </button>
        )}
        <button
          className={`${styles.btn} ${styles.btnGhost}`}
          onClick={reset}
          type="button"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
