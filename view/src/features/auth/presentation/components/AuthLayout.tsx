// ─── AuthLayout ────────────────────────────────────────────────
// Minimal centered layout for the /login, /register, /verify pages.
// Dark surface card on the base background, no shadows (DESIGN.md).

import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-base px-4">
      <div className="w-full max-w-sm rounded-md border border-border bg-surface px-6 py-8">
        {children}
      </div>
    </div>
  );
}