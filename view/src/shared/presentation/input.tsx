"use client";

import type { InputHTMLAttributes } from "react";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className = "", ...props }: InputProps) {
  return (
    <input
      className={`w-full h-9 px-3 rounded-[8px] bg-surface text-primary text-sm border border-border placeholder:text-muted transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none ${className}`}
      {...props}
    />
  );
}
