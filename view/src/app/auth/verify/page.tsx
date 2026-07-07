"use client";

// ─── Verify Email Page ────────────────────────────────────────
// Reads `?token=...&email=<urlencoded>` query params (the backend
// requires BOTH email and token in the body), calls POST
// /auth/verify-email, and shows success / failure. The email link
// uses `https://<frontend>/auth/verify?token=...&email=<urlencoded>`.

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/application/use-auth";
import { AuthLayout } from "@/features/auth/presentation/components/AuthLayout";

type VerifyState = "pending" | "success" | "error";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const email = searchParams.get("email");
  const [state, setState] = useState<VerifyState>("pending");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  // 4R CRITICAL 2 — call the AuthProvider's verifyEmail so the auth
  // context is updated with the verified user the backend returns.
  // The provider dispatches USER_UPDATED, so the banner disappears and
  // the save gate opens without a second GET /auth/me round-trip.
  const { verifyEmail } = useAuth();

  useEffect(() => {
    if (!token || !email) {
      setState("error");
      setErrorCode("invalid_token");
      return;
    }
    let cancelled = false;
    verifyEmail(email, token)
      .then(() => {
        if (!cancelled) setState("success");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const code = (err as { code?: string })?.code ?? "invalid_token";
        setState("error");
        setErrorCode(code);
      });
    return () => {
      cancelled = true;
    };
  }, [token, email, verifyEmail]);

  if (state === "success") {
    return (
      <AuthLayout>
        <h1 className="mb-4 text-xl font-medium text-primary">Email verified</h1>
        <p className="text-[13px] text-muted">
          Your email is verified. You can now save projects.
        </p>
        <p className="mt-6 text-[13px] text-muted">
          <a href="/studio" className="text-accent hover:underline">Back to studio</a>
        </p>
      </AuthLayout>
    );
  }

  if (state === "error") {
    return (
      <AuthLayout>
        <h1 className="mb-4 text-xl font-medium text-primary">Verification failed</h1>
        <p role="alert" className="text-[13px] text-error">
          {errorCode === "token_expired"
            ? "This verification link has expired. Request a new one."
            : errorCode === "token_already_consumed"
              ? "This link has already been used."
              : "This verification link is invalid or has expired."}
        </p>
        <p className="mt-6 text-[13px] text-muted">
          <a href="/login" className="text-accent hover:underline">Back to sign in</a>
        </p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <h1 className="mb-4 text-xl font-medium text-primary">Verifying…</h1>
      <p className="text-[13px] text-muted">Confirming your email address.</p>
    </AuthLayout>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <AuthLayout>
        <h1 className="mb-4 text-xl font-medium text-primary">Verifying…</h1>
        <p className="text-[13px] text-muted">Confirming your email address.</p>
      </AuthLayout>
    }>
      <VerifyEmailInner />
    </Suspense>
  );
}