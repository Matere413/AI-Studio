"use client";

import type { ButtonHTMLAttributes } from "react";

export type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  "aria-label": string;
};

export function IconButton({
  className = "",
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center w-8 h-8 rounded-full bg-transparent text-primary/70 transition-all duration-studio ease-studio hover:bg-surface-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 ring-offset-base ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
