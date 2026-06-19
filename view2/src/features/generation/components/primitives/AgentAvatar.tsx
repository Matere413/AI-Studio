"use client";

import styles from "./AgentAvatar.module.css";

interface AgentAvatarProps {
  name: string;
  src?: string;
  className?: string;
}

function getInitials(name: string) {
  const initials = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return initials || "AG";
}

export function AgentAvatar({ name, src, className }: AgentAvatarProps) {
  if (src) {
    return (
      <span className={[styles.avatar, className].filter(Boolean).join(" ")}>
        <img alt={name} className={styles.image} src={src} />
      </span>
    );
  }

  return (
    <span
      aria-label={name}
      className={[styles.avatar, className].filter(Boolean).join(" ")}
      role="img"
    >
      {getInitials(name)}
    </span>
  );
}
