"use client";

import { useState, type ChangeEvent } from "react";
import type { GenerationFlowViewModel } from "../hooks/useGenerationFlow";
import { resizeImageIfNeeded } from "../utils/imageResize";
import styles from "./IdentitySettingsPanel.module.css";

const ACCEPTED_REFERENCE_TYPES = new Set(["image/png", "image/jpeg"]);

interface IdentitySettingsPanelProps {
  flow: GenerationFlowViewModel;
}

export default function IdentitySettingsPanel({ flow }: IdentitySettingsPanelProps) {
  const {
    parameters,
    referenceFaceUrl,
    referenceGallery,
    validationErrors,
    isRunning,
    setReferenceFaceUrl,
    addToGallery,
    clearReferenceFace,
  } = flow;
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isPreparingImage, setIsPreparingImage] = useState(false);
  const isIdentityWorkflow = parameters.workflow_name === "identidad_gguf";
  const isDisabled = !isIdentityWorkflow || isRunning;
  const inlineError = uploadError ?? validationErrors.referenceImage;

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!ACCEPTED_REFERENCE_TYPES.has(file.type)) {
      setUploadError("Only PNG and JPEG images are accepted");
      clearReferenceFace();
      return;
    }

    setUploadError(null);
    setIsPreparingImage(true);

    try {
      const resizedImage = await resizeImageIfNeeded(file);
      const dataUrl = await readAsDataUrl(resizedImage);
      setReferenceFaceUrl(dataUrl);
      addToGallery(dataUrl);
    } catch (error) {
      clearReferenceFace();
      setUploadError(
        error instanceof Error
          ? error.message
          : "Image must be under 10MB after compression"
      );
    } finally {
      setIsPreparingImage(false);
      event.target.value = "";
    }
  };

  const handleSelectGalleryImage = (url: string) => {
    setUploadError(null);
    setReferenceFaceUrl(url);
  };

  return (
    <section
      className={`${styles.panel} ${isDisabled ? styles.panelDisabled : ""}`}
      aria-label="Identity Settings"
      data-disabled={isDisabled ? "true" : undefined}
    >
      <div className={styles.header}>
        <span className={styles.eyebrow}>Identity Settings</span>
        <p className={styles.helperText}>
          Upload a pre-cropped face or reuse a session reference.
        </p>
      </div>

      {!isIdentityWorkflow && (
        <p className={styles.warning} role="status">
          Not applicable for this workflow
        </p>
      )}

      <div className={styles.section}>
        <label className={styles.label} htmlFor="identity-reference-input">
          Upload reference image
        </label>
        <input
          key={referenceFaceUrl ? "has-identity-image" : "no-identity-image"}
          id="identity-reference-input"
          className={styles.input}
          type="file"
          accept="image/png,image/jpeg"
          onChange={handleUpload}
          disabled={isDisabled || isPreparingImage}
        />
        <span className={styles.helperText}>PNG or JPEG. 5MB max, auto-compress up to 10MB.</span>
        {isPreparingImage && (
          <span className={styles.helperText} aria-live="polite">
            Preparing reference image...
          </span>
        )}
        {inlineError && <span className={styles.error}>{inlineError}</span>}
      </div>

      <div className={styles.section}>
        <span className={styles.label}>Session gallery</span>
        {referenceGallery.length === 0 ? (
          <p className={styles.emptyState}>No reference images yet</p>
        ) : (
          <div className={styles.galleryGrid}>
            {referenceGallery.map((url, index) => (
              <button
                key={url}
                className={`${styles.thumbnailButton} ${
                  referenceFaceUrl === url ? styles.thumbnailButtonActive : ""
                }`}
                type="button"
                onClick={() => handleSelectGalleryImage(url)}
                disabled={isDisabled}
                aria-label={`Select reference image ${index + 1}`}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- data URL previews are local, user-selected files */}
                <img src={url} alt="" className={styles.thumbnailImage} />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <span className={styles.label}>Preview</span>
        {referenceFaceUrl ? (
          <div className={styles.previewFrame}>
            {/* eslint-disable-next-line @next/next/no-img-element -- data URL previews are local, user-selected files */}
            <img
              className={styles.previewImage}
              src={referenceFaceUrl}
              alt="Selected identity reference"
            />
            {isIdentityWorkflow && (
              <button
                className={styles.removeButton}
                type="button"
                onClick={clearReferenceFace}
                disabled={isRunning}
              >
                Remove
              </button>
            )}
          </div>
        ) : (
          <p className={styles.emptyState}>No reference selected</p>
        )}
      </div>
    </section>
  );
}

function readAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("Could not read image"));
    };
    reader.onerror = () => reject(new Error("Could not read image"));
    reader.readAsDataURL(blob);
  });
}
