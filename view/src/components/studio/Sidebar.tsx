"use client";

import { useCallback } from "react";
import { useGenerationStore, type JobEvent } from "@/stores/generationStore";
import { submitGenerate, getWsUrl, connectWebSocket } from "@/lib/api";
import styles from "./Sidebar.module.css";

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

export default function Sidebar() {
  const prompt = useGenerationStore((s) => s.prompt);
  const parameters = useGenerationStore((s) => s.parameters);
  const generationState = useGenerationStore((s) => s.generationState);
  const validationErrors = useGenerationStore((s) => s.validationErrors);
  const setPrompt = useGenerationStore((s) => s.setPrompt);
  const setParameters = useGenerationStore((s) => s.setParameters);
  const startConnecting = useGenerationStore((s) => s.startConnecting);
  const addEvent = useGenerationStore((s) => s.addEvent);
  const fail = useGenerationStore((s) => s.fail);
  const cancel = useGenerationStore((s) => s.cancel);
  const reset = useGenerationStore((s) => s.reset);

  const isRunning =
    generationState === "connecting" || generationState === "generating";
  const hasErrors =
    validationErrors.prompt || validationErrors.parameters;
  const isProductWorkflow = parameters.workflow_name === "product_premium";
  const selectedFormat = parameters.format ?? "square";

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim() || hasErrors) return;

    try {
      const response = await submitGenerate(prompt, parameters);
      startConnecting(response.job_id);

      const wsUrl = getWsUrl(response.job_id);
      const cleanup = connectWebSocket(wsUrl, {
        onEvent: (event) => addEvent(event as JobEvent),
        onExhausted: () => fail("Connection lost — please try again"),
        maxRetries: 3,
      });

      // Store the cleanup so cancel/reset can close the WebSocket
      useGenerationStore.setState({ _wsCleanup: cleanup });
    } catch (err) {
      fail(err instanceof Error ? err.message : "Generation failed");
    }
  }, [prompt, parameters, hasErrors, startConnecting, addEvent, fail]);

  const handleCancel = useCallback(() => {
    cancel(); // cancel already calls _wsCleanup internally
  }, [cancel]);

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
            onClick={handleCancel}
            type="button"
          >
            Cancel
          </button>
        ) : (
          <button
            className={`${styles.btn} ${styles.btnPrimary}`}
            onClick={handleGenerate}
            disabled={!!hasErrors || !prompt.trim()}
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
