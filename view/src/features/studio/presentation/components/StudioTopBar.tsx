interface StudioTopBarProps {
  onToggleAssets?: () => void;
  assetsExpanded?: boolean;
}

export function StudioTopBar({
  onToggleAssets,
  assetsExpanded,
}: StudioTopBarProps) {
  return (
    <header className="flex h-12 flex-shrink-0 items-center gap-6 border-b border-border px-4">
      <h1 className="text-sm font-medium text-primary">I-Studio Workspace</h1>
      <div role="tablist">
        <button
          role="tab"
          id="tab-studio-canvas"
          aria-selected="true"
          aria-controls="panel-studio-canvas"
          className="flex h-12 items-center border-b-2 border-accent bg-transparent px-0 text-accent"
        >
          Studio Canvas
        </button>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <button
          className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-surface px-3 text-[12px] font-medium tracking-ui text-accent transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
          onClick={onToggleAssets}
          aria-expanded={assetsExpanded}
          aria-controls="assets-drawer"
        >
          Assets
        </button>
        <button className="inline-flex h-7 items-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight">
          Export
        </button>
        <button className="inline-flex h-7 items-center gap-1.5 rounded-full border border-transparent bg-accent px-3 text-[12px] font-medium tracking-ui text-base transition-colors duration-studio ease-studio hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight focus-visible:ring-offset-2 ring-offset-base">
          Publish
        </button>
      </div>
    </header>
  );
}
