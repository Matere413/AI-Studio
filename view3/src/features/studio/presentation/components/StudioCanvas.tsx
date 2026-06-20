import { IconButton, ImageIcon, SearchIcon, FitToScreenIcon } from "@/shared/presentation";
import { StatusBar } from "./StatusBar";

export function StudioCanvas() {
  return (
    <section
      role="tabpanel"
      id="panel-studio-canvas"
      aria-labelledby="tab-studio-canvas"
      className="flex min-w-0 flex-1 flex-col"
    >
      {/* canvas meta bar */}
      <header className="flex h-[53px] flex-shrink-0 items-center justify-between border-b border-border px-4">
        <span className="font-mono text-[11px] leading-[1.4] text-muted">
          output_9348.png (1024x1024) - GENERATING
        </span>
        <div className="flex gap-2">
          <IconButton aria-label="Zoom Out">
            <SearchIcon size={14} />
          </IconButton>
          <IconButton aria-label="Fit to Screen">
            <FitToScreenIcon size={14} />
          </IconButton>
        </div>
      </header>

      {/* canvas stage — inline SVG dot-grid using fill-border (token-safe, no raw hex) */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-base">
        {/* SVG pattern layer: uses Tailwind fill-border token, zero CSS gradients */}
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          <defs>
            <pattern id="dot-grid" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
              <circle cx="10" cy="10" r="0.75" className="fill-border" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dot-grid)" />
        </svg>
        <StatusBar />

        {/* output frame */}
        <div className="relative flex aspect-square w-[min(400px,62vw)] items-center justify-center overflow-hidden border border-border bg-base">
          {/* accent border overlay */}
          <div className="pointer-events-none absolute inset-0 border-b border-accent" />
          <div className="z-[1] flex flex-col items-center gap-3 text-muted">
            <ImageIcon size={24} />
            <span className="text-[13px]">[ Minimalist coffee cup on concrete ]</span>
          </div>
        </div>
      </div>
    </section>
  );
}
