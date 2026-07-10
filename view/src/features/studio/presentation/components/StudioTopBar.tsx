"use client";

// ─── StudioTopBar ─────────────────────────────────────────────
// Top bar of the studio. Hosts the assets toggle, export/publish
// controls, and (when authenticated) the email-verification banner
// + log-out button. Anonymous users see the standard bar with no
// auth chrome — generation stays public.

import { useState } from "react";
import { useAuth } from "@/features/auth/application/use-auth";
import { EmailVerificationBanner } from "@/features/auth/presentation/components/EmailVerificationBanner";
import Link from "next/link";

interface StudioTopBarProps {
  onToggleAssets?: () => void;
  assetsExpanded?: boolean;
}

export function StudioTopBar({
  onToggleAssets,
  assetsExpanded,
}: StudioTopBarProps) {
  const { isAuthenticated, isVerified, resendVerification, logout } = useAuth();
  const [resending, setResending] = useState(false);

  async function handleResend() {
    setResending(true);
    try {
      await resendVerification();
    } finally {
      setResending(false);
    }
  }

  return (
    <header className="flex h-12 flex-shrink-0 items-center gap-6 border-b border-border px-4">
      <h1 className="text-sm font-medium text-primary">I-Studio Workspace</h1>
      <div role="tablist">
        <button
          role="tab"
          id="tab-studio-canvas"
          aria-selected="true"
          aria-controls="panel-studio-canvas"
          className="flex h-12 items-center border-b-2 border-accent bg-transparent px-0 text-accent"
        >
          Studio Canvas
        </button>
      </div>
      <div className="ml-auto flex items-center gap-2">
        {isAuthenticated && !isVerified && (
          <EmailVerificationBanner
            shown
            onResend={handleResend}
            resending={resending}
          />
        )}
        <button
          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-surface px-3 text-[12px] font-medium tracking-ui text-accent transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
          onClick={onToggleAssets}
          aria-expanded={assetsExpanded}
          aria-controls="assets-drawer"
        >
          Assets
        </button>
        <button className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight">
          Export
        </button>
        {isAuthenticated ? (
          <button
            aria-label="Log out"
            data-state="authenticated"
            onClick={logout}
            className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Log out
          </button>
        ) : (
          <Link
            href="/login"
            aria-label="Sign in"
            data-state="anonymous"
            className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M15 21H19a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H15" />
              <polyline points="8 17 3 12 8 7" />
              <line x1="3" y1="12" x2="15" y2="12" />
            </svg>
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}