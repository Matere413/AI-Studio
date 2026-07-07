"use client";

// ─── RegisterForm ──────────────────────────────────────────────
// Email + password + confirm form. POSTs to /auth/register via
// useAuth().register. On success redirects to a safe `next` query
// param or `/studio` (spec: no onboarding screen). Maps backend error
// codes (email_taken, weak_password) to inline messages.

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/application/use-auth";
import { sanitizeNext } from "@/features/auth/presentation/utils/sanitize-next";
import { AuthLayout } from "./AuthLayout";

// Backend strength contract: >=12, <=128, one letter, one digit.
function isStrongPassword(pw: string): boolean {
  if (pw.length < 12 || pw.length > 128) return false;
  if (!/[a-zA-Z]/.test(pw)) return false;
  if (!/[0-9]/.test(pw)) return false;
  return true;
}

function mapErrorCode(code: string | null): string {
  switch (code) {
    case "email_taken":
      return "Email already registered.";
    case "weak_password":
      return "Password must be at least 12 characters with a letter and a digit.";
    case "rate_limited":
      return "Too many attempts. Try again shortly.";
    default:
      return code ? "Registration failed. Please try again." : "";
  }
}

export function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { register, error } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: { preventDefault: () => void }) {
    e.preventDefault();
    setLocalError(null);
    if (!email.trim()) {
      setLocalError("Enter your email.");
      return;
    }
    if (!isStrongPassword(password)) {
      setLocalError("Password must be at least 12 characters with a letter and a digit.");
      return;
    }
    if (password !== confirm) {
      setLocalError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    const ok = await register(email.trim(), password);
    setSubmitting(false);
    if (ok) {
      const dest = sanitizeNext(searchParams.get("next")) ?? "/studio";
      router.push(dest);
    }
  }

  const shownError = localError ?? mapErrorCode(error);

  return (
    <AuthLayout>
      <h1 className="mb-6 text-xl font-medium text-primary">Create account</h1>
      <form
        onSubmit={(e) => { e.preventDefault(); void handleSubmit(e); }}
        className="flex flex-col gap-4"
      >
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] tracking-ui text-muted">Email</span>
          <input
            aria-label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-9 rounded-md border border-border bg-base px-3 text-sm text-primary placeholder:text-muted transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none"
            placeholder="you@example.com"
            autoComplete="email"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] tracking-ui text-muted">Password</span>
          <input
            aria-label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-9 rounded-md border border-border bg-base px-3 text-sm text-primary placeholder:text-muted transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none"
            placeholder="At least 12 characters"
            autoComplete="new-password"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] tracking-ui text-muted">Confirm password</span>
          <input
            aria-label="Confirm password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="h-9 rounded-md border border-border bg-base px-3 text-sm text-primary placeholder:text-muted transition-colors duration-studio ease-studio focus:border-highlight focus:outline-none"
            placeholder="Repeat your password"
            autoComplete="new-password"
          />
        </label>
        {shownError && (
          <p role="alert" className="text-[13px] text-error">{shownError}</p>
        )}
        <button
          aria-label="Register"
          type="submit"
          disabled={submitting}
          className="inline-flex h-9 items-center justify-center rounded-full bg-accent px-5 text-sm font-medium text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 focus-visible:ring-offset-base disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="mt-6 text-[13px] text-muted">
        Have an account?{" "}
        <a href="/login" className="text-accent hover:underline">Sign in</a>
      </p>
    </AuthLayout>
  );
}