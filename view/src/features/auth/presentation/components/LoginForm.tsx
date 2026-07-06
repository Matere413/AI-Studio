"use client";

// ─── LoginForm ─────────────────────────────────────────────────
// Email + password form. POSTs to /auth/login via useAuth().login.
// On success redirects to the `next` query param or `/`.
// Maps backend error codes (invalid_credentials, email_taken, weak_password)
// to inline user messages.

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/application/use-auth";
import { AuthLayout } from "./AuthLayout";

function mapErrorCode(code: string | null): string {
  switch (code) {
    case "invalid_credentials":
      return "Invalid email or password.";
    case "email_taken":
      return "Email already registered.";
    case "weak_password":
      return "Password is too weak.";
    case "unauthenticated":
      return "Invalid email or password.";
    default:
      return code ? "Sign-in failed. Please try again." : "";
  }
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, error } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: { preventDefault: () => void }) {
    e.preventDefault();
    setLocalError(null);
    if (!email.trim() || !password) {
      setLocalError("Enter your email and password.");
      return;
    }
    setSubmitting(true);
    const ok = await login(email.trim(), password);
    setSubmitting(false);
    if (ok) {
      const next = searchParams.get("next") ?? "/";
      router.push(next);
    }
  }

  const shownError = localError ?? mapErrorCode(error);

  return (
    <AuthLayout>
      <h1 className="mb-6 text-xl font-medium text-primary">Sign in</h1>
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
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </label>
        {shownError && (
          <p role="alert" className="text-[13px] text-error">{shownError}</p>
        )}
        <button
          aria-label="Log in"
          type="submit"
          disabled={submitting}
          className="inline-flex h-9 items-center justify-center rounded-full bg-accent px-5 text-sm font-medium text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 focus-visible:ring-offset-base disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-[13px] text-muted">
        No account?{" "}
        <a href="/register" className="text-accent hover:underline">Register</a>
      </p>
    </AuthLayout>
  );
}