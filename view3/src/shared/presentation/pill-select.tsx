"use client";

import type { SelectHTMLAttributes } from "react";

export type PillSelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export function PillSelect({ className = "", children, ...props }: PillSelectProps) {
  return (
    <select
      className={`h-[22px] px-2 rounded-full bg-surface text-primary text-[10px] leading-none font-mono border border-border appearance-none cursor-pointer transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}
