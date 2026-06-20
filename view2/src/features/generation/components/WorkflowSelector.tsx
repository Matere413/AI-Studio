"use client";

import { useEffect, useState } from "react";
import Pill from "@/shared/components/ui/Pill";
import { WORKFLOW_NAMES } from "../api/types";
import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

export default function WorkflowSelector() {
  const workflowName = useGenerationStore((state) => state.parameters.workflow_name) ?? "flux2_txt2img";
  const setParameters = useGenerationStore((state) => state.setParameters);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!useGenerationStore.getState().parameters.workflow_name) {
      setParameters({ workflow_name: "flux2_txt2img" });
    }
  }, [setParameters]);

  return (
    <div className={styles.listboxField}>
      <Pill
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Workflow: ${workflowName}`}
        onClick={() => setOpen((value) => !value)}
        selected={open}
      >
        Workflow: {workflowName}
      </Pill>

      {open ? (
        <div className={styles.listboxMenu} role="listbox" aria-label="Workflow options">
          {WORKFLOW_NAMES.map((workflow) => (
            <button
              key={workflow}
              className={styles.listboxOption}
              role="option"
              aria-selected={workflow === workflowName}
              onClick={() => {
                setParameters({ workflow_name: workflow });
                setOpen(false);
              }}
              type="button"
            >
              {workflow}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
