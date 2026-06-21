import { FileIcon, ImageIcon, CloseIcon } from "@/shared/presentation";
import type { Asset } from "@/app/studio-state";

interface AssetListProps {
  assets: Asset[];
  onRemoveAsset: (id: string) => void;
}

export function AssetList({ assets, onRemoveAsset }: AssetListProps) {
  return (
    <div className="p-2">
      {assets.map((asset) => (
        <div
          key={asset.id}
          className="flex items-center gap-2 rounded-xl p-2 transition-colors duration-studio ease-studio hover:bg-surface"
        >
          <div className="grid size-8 place-items-center rounded-[8px] bg-surface text-muted">
            {asset.type === "file" ? <FileIcon size={16} /> : <ImageIcon size={16} />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-primary">{asset.name}</div>
            <div className="text-[11px] tracking-ui text-muted">{asset.addedAt}</div>
          </div>
          <button
            onClick={() => onRemoveAsset(asset.id)}
            className="flex size-6 items-center justify-center rounded-full text-muted hover:bg-red-100 hover:text-red-500 transition-colors duration-studio"
            aria-label={`Remove ${asset.name}`}
          >
            <CloseIcon size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
