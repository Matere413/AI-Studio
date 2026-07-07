"use client";

// ─── LogoutButton ──────────────────────────────────────────────
// Ghost button for the top bar. Calls onLogout when activated.
// DESIGN.md: dark mode, no shadows, amber accent on hover, 150ms motion.

export function LogoutButton({ onLogout }: { onLogout: () => void }) {
  return (
    <button
      aria-label="Log out"
      onClick={onLogout}
      className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary/70 transition-colors duration-studio ease-studio hover:bg-surface-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <polyline points="16 17 21 12 16 7" />
        <line x1="21" y1="12" x2="9" y2="12" />
      </svg>
      Log out
    </button>
  );
}