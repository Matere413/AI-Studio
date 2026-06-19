"use client";

import { useState, type ChangeEvent, type KeyboardEvent } from "react";
import styles from "./InputBar.module.css";

interface InputBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  validationError?: string;
}

export function InputBar({
  value,
  onChange,
  onSubmit,
  disabled = false,
  validationError,
}: InputBarProps) {
  const [localError, setLocalError] = useState<string | null>(null);
  const promptError = value.trim().length === 0 ? "Prompt is required" : null;
  const error = validationError ?? localError ?? promptError;
  const submitDisabled = disabled || Boolean(validationError) || value.trim().length === 0;

  const submit = () => {
    if (validationError) return;
    if (value.trim().length === 0) {
      setLocalError("Prompt is required");
      return;
    }

    setLocalError(null);
    onSubmit();
  };

  const handleChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    if (localError) setLocalError(null);
    onChange(event.target.value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className={styles.shell}>
      <div className={styles.fieldFrame}>
        <textarea
          aria-label="Prompt"
          className={`input ${styles.textarea}`}
          disabled={disabled}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Describe the campaign image to generate..."
          rows={2}
          value={value}
        />
        <button
          className={`btn btn-primary ${styles.sendButton}`}
          disabled={submitDisabled}
          onClick={submit}
          type="button"
        >
          Send prompt
        </button>
      </div>
      {error ? (
        <p className={`text-mono ${styles.error}`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
