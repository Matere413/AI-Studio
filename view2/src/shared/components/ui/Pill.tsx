import type { ButtonHTMLAttributes, PropsWithChildren } from "react";
import styles from "@/features/generation/components/GenerationStudio.module.css";

type PillProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> & {
  selected?: boolean;
};

export default function Pill({ children, selected, type = "button", ...props }: PillProps) {
  return (
    <button
      className={styles.pill}
      data-selected={selected ? "true" : "false"}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
