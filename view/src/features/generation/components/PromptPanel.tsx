"use client";

import { useState, type ChangeEvent } from "react";
import type { GenerationFlowViewModel } from "../hooks/useGenerationFlow";
import styles from "./PromptPanel.module.css";

const WORKFLOWS = [
  { value: "qwen_txt2img" as const, label: "Qwen T2I" },
  { value: "txt2img" as const, label: "TXT → IMG" },
  { value: "img2img" as const, label: "IMG → IMG" },
  { value: "controlnet" as const, label: "ControlNet" },
  { value: "product_premium" as const, label: "Product" },
  { value: "realistic_persona" as const, label: "Persona" },
];

const PRODUCT_FORMATS = [
  { value: "square" as const, label: "Square" },
  { value: "vertical" as const, label: "Vertical" },
];

const GENDER_OPTIONS = [
  { value: "woman", label: "Woman" },
  { value: "man", label: "Man" },
  { value: "nonbinary", label: "Nonbinary" },
];

const ETHNICITY_OPTIONS = [
  { value: "latina", label: "Latina" },
  { value: "east_asian", label: "East Asian" },
  { value: "black", label: "Black" },
  { value: "white", label: "White" },
  { value: "middle_eastern", label: "Middle Eastern" },
  { value: "south_asian", label: "South Asian" },
];

const WARDROBE_OPTIONS = [
  { value: "linen blazer", label: "Linen blazer" },
  { value: "wool coat", label: "Wool coat" },
  { value: "tailored linen suit", label: "Tailored linen suit" },
  { value: "casual shirt", label: "Casual shirt" },
  { value: "evening dress", label: "Evening dress" },
];

const EXPRESSION_OPTIONS = [
  { value: "soft smile", label: "Soft smile" },
  { value: "thoughtful", label: "Thoughtful" },
  { value: "confident half-smile", label: "Confident half-smile" },
  { value: "neutral", label: "Neutral" },
  { value: "calm smile", label: "Calm smile" },
];

const BACKGROUND_OPTIONS = [
  { value: "warm studio", label: "Warm studio" },
  { value: "city street", label: "City street" },
  { value: "sunlit studio", label: "Sunlit studio" },
  { value: "neutral backdrop", label: "Neutral backdrop" },
  { value: "editorial interior", label: "Editorial interior" },
];

const PERSONA_OUTPUT_TYPES = [
  { value: "portrait" as const, label: "Portrait" },
  { value: "full-body" as const, label: "Full body" },
  { value: "lifestyle" as const, label: "Lifestyle" },
  { value: "editorial" as const, label: "Editorial" },
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
  const isProductWorkflow = parameters.workflow_name === "product_premium";
  const isPersonaWorkflow = parameters.workflow_name === "realistic_persona";
  const isQwenWorkflow = parameters.workflow_name === "qwen_txt2img";
  const selectedFormat = parameters.format ?? "square";
  const selectedAge = parameters.age ?? 35;
  const selectedOutputType = parameters.output_type ?? "portrait";
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
                setParameters(
                  wf.value === "product_premium"
                    ? { workflow_name: wf.value, format: parameters.format ?? "square" }
                    : wf.value === "realistic_persona"
                    ? {
                        workflow_name: wf.value,
                        age: selectedAge,
                        output_type: selectedOutputType,
                      }
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

      {isPersonaWorkflow ? (
        <>
          <div className={styles.section}>
            <label className={styles.label} htmlFor="reference-face-input">
              Reference face <span className={styles.optional}>(optional)</span>
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
              PNG or JPEG, 10MB max. Leave empty for prompt-only generation.
            </span>
            {isReferenceFaceLoading && (
              <span className={styles.helperText} aria-live="polite">
                Preparing reference face...
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
                  alt="Reference face preview"
                />
                <button
                  className={`${styles.btn} ${styles.btnGhost}`}
                  onClick={handleReferenceFaceRemove}
                  disabled={isRunning}
                  type="button"
                >
                  Remove reference face
                </button>
              </div>
            )}
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-age">
              Age: {selectedAge || 35}
            </label>
            <input
              id="persona-age"
              className={styles.input}
              type="range"
              min={18}
              max={100}
              value={selectedAge || 35}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  age: Number(e.target.value),
                })
              }
              disabled={isRunning}
            />
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-gender">
              Gender
            </label>
            <select
              id="persona-gender"
              className={styles.input}
              value={parameters.gender || ""}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  gender: e.target.value,
                })
              }
              disabled={isRunning}
            >
              <option value="">Default</option>
              {GENDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-ethnicity">
              Ethnicity
            </label>
            <select
              id="persona-ethnicity"
              className={styles.input}
              value={parameters.ethnicity || ""}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  ethnicity: e.target.value,
                })
              }
              disabled={isRunning}
            >
              <option value="">Default</option>
              {ETHNICITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-wardrobe">
              Wardrobe
            </label>
            <select
              id="persona-wardrobe"
              className={styles.input}
              value={parameters.wardrobe || ""}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  wardrobe: e.target.value,
                })
              }
              disabled={isRunning}
            >
              <option value="">Default</option>
              {WARDROBE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-expression">
              Expression
            </label>
            <select
              id="persona-expression"
              className={styles.input}
              value={parameters.expression || ""}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  expression: e.target.value,
                })
              }
              disabled={isRunning}
            >
              <option value="">Default</option>
              {EXPRESSION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.section}>
            <label className={styles.label} htmlFor="persona-background">
              Background
            </label>
            <select
              id="persona-background"
              className={styles.input}
              value={parameters.background || ""}
              onChange={(e) =>
                setParameters({
                  workflow_name: "realistic_persona",
                  background: e.target.value,
                })
              }
              disabled={isRunning}
            >
              <option value="">Default</option>
              {BACKGROUND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <fieldset className={styles.section}>
            <legend className={styles.label}>Output type</legend>
            <div className={styles.radioGroup}>
              {PERSONA_OUTPUT_TYPES.map((outputType) => (
                <label key={outputType.value} className={styles.radioOption}>
                  <input
                    type="radio"
                    name="persona-output-type"
                    value={outputType.value}
                    checked={selectedOutputType === outputType.value}
                    onChange={() =>
                      setParameters({
                        workflow_name: "realistic_persona",
                        output_type: outputType.value,
                      })
                    }
                    disabled={isRunning}
                  />
                  {outputType.label}
                </label>
              ))}
            </div>
          </fieldset>
        </>
      ) : isQwenWorkflow ? (
        <>
          <div className={styles.section}>
            <label className={styles.label} htmlFor="qwen-width">Width: {parameters.width ?? 1024}</label>
            <input
              id="qwen-width"
              className={styles.input}
              type="range"
              min={512}
              max={1536}
              step={64}
              value={parameters.width ?? 1024}
              onChange={(e) => setParameters({ width: Number(e.target.value) })}
              disabled={isRunning}
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label} htmlFor="qwen-height">Height: {parameters.height ?? 1024}</label>
            <input
              id="qwen-height"
              className={styles.input}
              type="range"
              min={512}
              max={1536}
              step={64}
              value={parameters.height ?? 1024}
              onChange={(e) => setParameters({ height: Number(e.target.value) })}
              disabled={isRunning}
            />
          </div>
          <div className={styles.section}>
            <label className={styles.label}>Quality Mode</label>
            <div className={styles.chipGroup}>
              <button
                className={`${styles.chip} ${(parameters.quality_mode ?? "fast") === "fast" ? styles.chipOn : ""}`}
                onClick={() => setParameters({ quality_mode: "fast" })}
                disabled={isRunning}
                type="button"
              >
                Fast (4 steps)
              </button>
              <button
                className={`${styles.chip} ${(parameters.quality_mode ?? "fast") === "high" ? styles.chipOn : ""}`}
                onClick={() => setParameters({ quality_mode: "high" })}
                disabled={isRunning}
                type="button"
              >
                High (50 steps)
              </button>
            </div>
          </div>
        </>
      ) : isProductWorkflow ? (
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
              value={parameters.checkpoint_url || ""}
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
              value={parameters.lora_url || ""}
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
