"use client";

import { useState, type ChangeEvent } from "react";
import type { GenerationFlowViewModel } from "../hooks/useGenerationFlow";
import styles from "./PromptPanel.module.css";

const WORKFLOWS = [
  { value: "flux2_txt2img" as const, label: "Flux 2 T2I" },
  { value: "flux2_editing" as const, label: "Flux 2 Edit" },
  { value: "identidad_gguf" as const, label: "Identity" },
];

const MAX_REFERENCE_FACE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_REFERENCE_FACE_TYPES = new Set(["image/png", "image/jpeg"]);

interface PromptPanelProps {
  flow: GenerationFlowViewModel;
}

export default function PromptPanel({ flow }: PromptPanelProps) {
  const {
    prompt,
    parameters,
    referenceFaceUrl,
    validationErrors,
    isRunning,
    hasErrors,
    setPrompt,
    setParameters,
    setReferenceFaceUrl,
    clearReferenceFace,
    generate,
    cancel,
    reset,
  } = flow;
  const isIdentityWorkflow = parameters.workflow_name === "identidad_gguf";
  const isEditingWorkflow = parameters.workflow_name === "flux2_editing";
  const isFlux2Workflow = parameters.workflow_name === "flux2_txt2img" || parameters.workflow_name === "flux2_editing";
  const isTurboOn = parameters.use_turbo ?? true;
  const [referenceFaceError, setReferenceFaceError] = useState<string | null>(null);
  const [isReferenceFaceLoading, setIsReferenceFaceLoading] = useState(false);

  const handleReferenceFaceChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!ACCEPTED_REFERENCE_FACE_TYPES.has(file.type)) {
      setReferenceFaceError("Only PNG and JPEG images are accepted");
      clearReferenceFace();
      return;
    }

    if (file.size > MAX_REFERENCE_FACE_BYTES) {
      setReferenceFaceError("Image must be under 10MB");
      clearReferenceFace();
      return;
    }

    setReferenceFaceError(null);
    setIsReferenceFaceLoading(true);

    const reader = new FileReader();
    reader.onload = () => {
      setIsReferenceFaceLoading(false);
      if (typeof reader.result === "string") {
        setReferenceFaceUrl(reader.result);
        return;
      }
      setReferenceFaceError("Could not read image");
      clearReferenceFace();
    };
    reader.onerror = () => {
      setIsReferenceFaceLoading(false);
      setReferenceFaceError("Could not read image");
      clearReferenceFace();
    };
    reader.readAsDataURL(file);
  };

  const handleReferenceFaceRemove = () => {
    setReferenceFaceError(null);
    clearReferenceFace();
  };

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
          value={prompt || ""}
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
          {WORKFLOWS.map((wf) => (
            <button
              key={wf.value}
              className={`${styles.chip} ${
                parameters.workflow_name === wf.value ? styles.chipOn : ""
              }`}
              onClick={() =>
                setParameters({ workflow_name: wf.value })
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

      <div
        className={`${styles.section} ${!isFlux2Workflow ? styles.sectionHidden : ""}`}
        data-testid="turbo-section"
        data-hidden={isFlux2Workflow ? undefined : "true"}
        aria-hidden={!isFlux2Workflow}
        {...(!isFlux2Workflow ? { inert: true } : {})}
      >
        <label className={styles.label} htmlFor="turbo-toggle">
          Turbo Mode
        </label>
        <div className={styles.toggleRow}>
          <button
            id="turbo-toggle"
            className={`${styles.btn} ${isTurboOn ? styles.btnPrimary : styles.btnGhost}`}
            onClick={() => setParameters({ use_turbo: !isTurboOn })}
            disabled={isRunning}
            type="button"
          >
            {isTurboOn ? "Turbo On (4 steps)" : "Turbo Off (50 steps)"}
          </button>
        </div>
      </div>

      <div
        className={`${styles.section} ${!(isEditingWorkflow || isIdentityWorkflow) ? styles.sectionHidden : ""}`}
        data-testid="reference-section"
        data-hidden={(isEditingWorkflow || isIdentityWorkflow) ? undefined : "true"}
        aria-hidden={!(isEditingWorkflow || isIdentityWorkflow)}
        {...(!(isEditingWorkflow || isIdentityWorkflow) ? { inert: true } : {})}
      >
        <label className={styles.label} htmlFor="reference-face-input">
          Reference image {isEditingWorkflow ? <span className={styles.optional}>(required for editing)</span> : <span className={styles.optional}>(optional)</span>}
        </label>
        <input
          key={referenceFaceUrl ? "has-image" : "no-image"}
          id="reference-face-input"
          className={styles.input}
          type="file"
          accept="image/png,image/jpeg"
          onChange={handleReferenceFaceChange}
          disabled={isRunning || isReferenceFaceLoading}
        />
        <span className={styles.helperText}>
          PNG or JPEG, 10MB max.
        </span>
        {isReferenceFaceLoading && (
          <span className={styles.helperText} aria-live="polite">
            Preparing image...
          </span>
        )}
        {referenceFaceError && (
          <span className={styles.error}>{referenceFaceError}</span>
        )}
        {referenceFaceUrl && (
          <div className={styles.referencePreview}>
            <img
              className={styles.referenceImage}
              src={referenceFaceUrl}
              alt="Reference image preview"
            />
            <button
              className={`${styles.btn} ${styles.btnGhost}`}
              onClick={handleReferenceFaceRemove}
              disabled={isRunning}
              type="button"
            >
              Remove reference image
            </button>
          </div>
        )}
      </div>

      {isIdentityWorkflow && (
        <div className={styles.section}>
          <span className={styles.helperText}>
            Identity model preserves facial features from the reference image.
          </span>
        </div>
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