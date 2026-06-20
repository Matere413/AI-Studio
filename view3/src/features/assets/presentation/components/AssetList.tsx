import { FileIcon, ImageIcon } from "@/shared/presentation";
import type { MockAsset } from "@/shared/presentation";

interface AssetListProps {
  assets: MockAsset[];
}

export function AssetList({ assets }: AssetListProps) {
  return (
    <div className="p-2">
      {assets.map((asset, i) => (
        <div
          key={i}
          className="flex items-center gap-2 rounded-xl p-2 transition-colors duration-studio ease-studio hover:bg-surface"
        >
          <div className="grid size-8 place-items-center rounded-[8px] bg-surface text-muted">
            {asset.type === "file" ? <FileIcon size={16} /> : <ImageIcon size={16} />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium text-primary">{asset.name}</div>
            <div className="text-[11px] tracking-ui text-muted">{asset.date}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
