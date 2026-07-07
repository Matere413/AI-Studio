// ─── Hero (presentational server component) ────────────────────
// Renders the landing hero block: eyebrow, headline, subhead, and the
// two CTAs (primary → /studio, secondary → /register) via next/link.
// No client hooks. All copy comes from the landing-copy data file.

import Link from "next/link";
import type { HeroCopy } from "../data/landing-copy";

export function Hero({ copy }: { copy: HeroCopy }) {
  return (
    <section className="flex flex-col gap-6">
      <p className="font-mono text-xs tracking-caps text-muted">{copy.eyebrow}</p>
      <h1 className="font-display text-2xl tracking-tight text-primary">
        {copy.headline}
      </h1>
      <p className="max-w-[58ch] text-sm leading-relaxed text-muted">
        {copy.subhead}
      </p>
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <Link
          href={copy.primaryCta.href}
          className="inline-flex h-9 items-center justify-center rounded-full bg-accent px-5 text-sm font-medium text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 focus-visible:ring-offset-base"
        >
          {copy.primaryCta.label}
        </Link>
        <Link
          href={copy.secondaryCta.href}
          className="inline-flex h-9 items-center justify-center rounded-full bg-transparent px-5 text-sm font-medium text-primary border border-border transition-colors duration-studio ease-studio hover:bg-surface-hover hover:border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
        >
          {copy.secondaryCta.label}
        </Link>
      </div>
    </section>
  );
}