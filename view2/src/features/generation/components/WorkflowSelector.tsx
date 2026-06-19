"use client";

import type { ChangeEvent } from "react";
import type { WorkflowName } from "../api/types";
import styles from "./WorkflowSelector.module.css";

const WORKFLOW_OPTIONS: Array<{ value: WorkflowName; label: string }> = [
  { value: "flux2_txt2img", label: "Base txt2img" },
  { value: "flux2_editing", label: "Flux editing" },
  { value: "identidad_gguf", label: "Identity GGUF" },
];

interface WorkflowSelectorProps {
  value?: WorkflowName;
  onChange: (value: WorkflowName) => void;
  disabled?: boolean;
}

export function WorkflowSelector({
  value = "flux2_txt2img",
  onChange,
  disabled = false,
}: WorkflowSelectorProps) {
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onChange(event.target.value as WorkflowName);
  };

  return (
    <select
      aria-label="Workflow"
      className={`input text-mono ${styles.selector}`}
      disabled={disabled}
      onChange={handleChange}
      value={value}
    >
      {WORKFLOW_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
