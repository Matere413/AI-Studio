"use client";

// ─── RegisterForm ──────────────────────────────────────────────
// Email + password + confirm form. POSTs to /auth/register via
// useAuth().register. On success shows "check your email" (no redirect
// — the backend issues cookies but the user is unverified). Maps
// backend error codes (email_taken, weak_password) to inline messages.

import { useState } from "react";
import { useAuth } from "@/features/auth/application/use-auth";
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
    default:
      return code ? "Registration failed. Please try again." : "";
  }
}

export function RegisterForm() {
  const { register, error } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

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
    if (ok) setDone(true);
  }

  const shownError = localError ?? mapErrorCode(error);

  if (done) {
    return (
      <AuthLayout>
        <h1 className="mb-4 text-xl font-medium text-primary">Check your email</h1>
        <p className="text-[13px] text-muted">
          We sent a verification link to <span className="text-primary">{email}</span>.
          Verify your email to save projects.
        </p>
        <p className="mt-6 text-[13px] text-muted">
          Already verified?{" "}
          <a href="/login" className="text-accent hover:underline">Sign in</a>
        </p>
      </AuthLayout>
    );
  }

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