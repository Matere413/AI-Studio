"use client";

import { useState } from "react";
import Pill from "@/shared/components/ui/Pill";
import { useGenerationStore } from "../stores/generationStore";
import styles from "./GenerationStudio.module.css";

const SPEEDS = [
  { label: "Turbo", value: true },
  { label: "Balanced", value: false },
] as const;

export default function SpeedSelector() {
  const useTurbo = useGenerationStore((state) => state.parameters.use_turbo) ?? true;
  const setParameters = useGenerationStore((state) => state.setParameters);
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.listboxField}>
      <Pill
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Speed: ${useTurbo ? "Turbo" : "Balanced"}`}
        onClick={() => setOpen((value) => !value)}
        selected={open}
      >
        Speed: {useTurbo ? "Turbo" : "Balanced"}
      </Pill>

      {open ? (
        <div className={styles.listboxMenu} role="listbox" aria-label="Speed options">
          {SPEEDS.map((speed) => (
            <button
              key={speed.label}
              className={styles.listboxOption}
              role="option"
              aria-selected={speed.value === useTurbo}
              onClick={() => {
                setParameters({ use_turbo: speed.value });
                setOpen(false);
              }}
              type="button"
            >
              {speed.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
