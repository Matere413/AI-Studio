import { Suspense } from "react";
import { RegisterForm } from "@/features/auth/presentation/components/RegisterForm";
import { AuthLayout } from "@/features/auth/presentation/components/AuthLayout";

// DESIGN.md-compliant Suspense fallback so the auth surface never
// flashes blank while the client bundle streams (useSearchParams is a
// client hook that triggers a Suspense boundary during prerender).
export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <AuthLayout>
          <h1 className="mb-4 text-xl font-medium text-primary">Create account</h1>
          <p className="text-[13px] text-muted">Loading…</p>
        </AuthLayout>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}