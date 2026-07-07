"use client";

// ─── StudioTopBar ─────────────────────────────────────────────
// Top bar of the studio. Hosts the assets toggle, export/publish
// controls, and (when authenticated) the email-verification banner
// + log-out button. Anonymous users see the standard bar with no
// auth chrome — generation stays public.

import { useState } from "react";
import { useAuth } from "@/features/auth/application/use-auth";
import { EmailVerificationBanner } from "@/features/auth/presentation/components/EmailVerificationBanner";
import { LogoutButton } from "@/features/auth/presentation/components/LogoutButton";

interface StudioTopBarProps {
  onToggleAssets?: () => void;
  assetsExpanded?: boolean;
}

export function StudioTopBar({
  onToggleAssets,
  assetsExpanded,
}: StudioTopBarProps) {
  const { user, isAuthenticated, isVerified, resendVerification, logout } = useAuth();
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
        <button className="inline-flex h-7 items-center gap-1.5 rounded-full border border-transparent bg-accent px-3 text-[12px] font-medium tracking-ui text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 ring-offset-base">
          Publish
        </button>
        {isAuthenticated && user && <LogoutButton onLogout={logout} />}
      </div>
    </header>
  );
}