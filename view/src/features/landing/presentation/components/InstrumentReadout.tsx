// ─── InstrumentReadout (presentational server component) ───────
// The landing's one memorable section: a mono-typeset "instrument
// readout" panel. No card grid, no hero-metric counters, no gradients
// (DESIGN.md + impeccable bans). Each line is a key/value pair set in
// the mono face, separated by dotted leaders — evoking a tool's
// status readout rather than a marketing grid.

import type { ReadoutCopy } from "../data/landing-copy";

export function InstrumentReadout({ copy }: { copy: ReadoutCopy }) {
  return (
    <section className="mt-18 flex flex-col gap-4 border-t border-border pt-8">
      <p className="font-mono text-xs tracking-caps text-muted">{copy.eyebrow}</p>
      <dl className="flex flex-col gap-2">
        {copy.lines.map((line) => (
          <div key={line} className="flex min-w-0 items-baseline">
            <dt className="font-mono text-sm text-primary whitespace-nowrap">{line}</dt>
          </div>
        ))}
      </dl>
    </section>
  );
}