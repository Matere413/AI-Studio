"use client";

import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-base hover:bg-amber-500 border border-transparent",
  secondary:
    "bg-transparent text-primary border border-border hover:bg-surface-hover hover:border-muted",
  ghost:
    "bg-transparent text-primary/70 border border-transparent hover:bg-surface-hover hover:text-primary",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center h-9 px-5 rounded-full text-sm font-medium transition-all duration-studio ease-studio focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 ring-offset-base ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
