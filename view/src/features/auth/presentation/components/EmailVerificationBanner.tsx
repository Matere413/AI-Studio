"use client";

// ─── EmailVerificationBanner ───────────────────────────────────
// Yellow banner (highlight #eab208 per DESIGN.md) shown in the top bar
// when isAuthenticated && !isVerified. Includes a resend control.
// Does NOT block generation.

export function EmailVerificationBanner({
  shown,
  onResend,
  resending = false,
}: {
  shown: boolean;
  onResend: () => void;
  resending?: boolean;
}) {
  if (!shown) return null;
  return (
    <div
      role="alert"
      className="flex items-center gap-3 rounded-md border border-highlight/40 bg-highlight/10 px-3 py-1.5 text-[12px] text-highlight"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M12 9v4" />
        <path d="M12 17h.01" />
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      </svg>
      <span>Verify your email to save projects.</span>
      <button
        aria-label="Resend verification email"
        onClick={onResend}
        disabled={resending}
        className="font-medium underline-offset-2 transition-colors duration-studio ease-studio hover:underline disabled:opacity-50"
      >
        {resending ? "Sending…" : "Resend"}
      </button>
    </div>
  );
}