// ─── Landing route (server component) ───────────────────────────
// Anonymous visitors land here. Server-rendered, no `useAuth` at the
// top level (spec: "Server-Rendered Landing Route", no hydration
// flash). Authenticated visitors still see the landing (no forced
// redirect to /studio).

import { LandingPage } from "@/features/landing/presentation/components/LandingPage";

export default function Page() {
  return <LandingPage />;
}