// ─── LandingPage (server component) ─────────────────────────────
// Composes the landing from presentational children. All copy is
// sourced from the landing-copy data file (spec: "Copy sourced from
// data file"). No client hooks, no auth hook at the top level (spec:
// "Server-Rendered Landing Route", "Authenticated visit still renders
// landing").

import { Hero } from "./Hero";
import { InstrumentReadout } from "./InstrumentReadout";
import { landingCopy } from "../data/landing-copy";

export function LandingPage() {
  return (
    <main className="min-h-screen bg-base text-primary">
      <div className="mx-auto flex max-w-3xl flex-col px-6 py-18">
        <Hero copy={landingCopy.hero} />
        <InstrumentReadout copy={landingCopy.readout} />
      </div>
    </main>
  );
}