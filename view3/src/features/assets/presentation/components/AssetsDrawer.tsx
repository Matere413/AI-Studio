import type { MockAsset } from "@/shared/presentation";
import { AssetList } from "./AssetList";

interface AssetsDrawerProps {
  assets: MockAsset[];
  isOpen: boolean;
}

export function AssetsDrawer({ assets, isOpen }: AssetsDrawerProps) {
  return (
    <aside
      id="assets-drawer"
      className={`flex w-[260px] flex-shrink-0 flex-col border-l border-border bg-base ${
        isOpen ? "flex" : "hidden"
      }`}
      aria-label="Context Assets"
    >
      {/* drawer header */}
      <header className="border-b border-border p-4">
        <h2 className="m-0 text-[13px] font-medium text-primary">Context Assets</h2>
        <p className="m-0 text-[11px] text-muted">Files referenced in this session.</p>
      </header>

      <AssetList assets={assets} />

      {/* upload button */}
      <footer className="mt-auto border-t border-border p-4">
        <button
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
        >
          + Upload Asset
        </button>
      </footer>
    </aside>
  );
}
