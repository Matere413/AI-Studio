"use client";

import { AgentIcon } from "./icons";

export type AvatarMarkProps = {
  size?: "md" | "sm";
  className?: string;
};

const sizeMap = {
  md: { container: "w-6 h-6", iconSize: 14 },
  sm: { container: "w-5 h-5", iconSize: 12 },
};

export function AvatarMark({ size = "md", className = "" }: AvatarMarkProps) {
  const { container, iconSize } = sizeMap[size];

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full bg-accent text-base flex-shrink-0 ${container} ${className}`}
      aria-hidden="true"
    >
      <AgentIcon size={iconSize} />
    </span>
  );
}
