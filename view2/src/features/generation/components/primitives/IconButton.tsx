"use client";

import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import styles from "./IconButton.module.css";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
}

export function IconButton({ label, children, className, type = "button", onBlur, onFocus, style, ...rest }: IconButtonProps) {
  const [focusVisible, setFocusVisible] = useState(false);

  return (
    <button
      {...rest}
      aria-label={label}
      className={[
        styles.button,
        "btn-icon-circle",
        focusVisible ? "focus-visible" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onBlur={(event) => {
        setFocusVisible(false);
        onBlur?.(event);
      }}
      onFocus={(event) => {
        setFocusVisible(true);
        onFocus?.(event);
      }}
      style={{ minHeight: "44px", minWidth: "44px", ...style }}
      title={label}
      type={type}
    >
      <span aria-hidden="true" className={styles.icon}>
        {children}
      </span>
    </button>
  );
}
