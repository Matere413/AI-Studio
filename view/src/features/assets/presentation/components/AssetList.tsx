import { FileIcon, ImageIcon, CloseIcon } from "@/shared/presentation";
import type { Asset } from "@/app/studio-state";
import type { UploadStatus } from "@/app/studio-state";

interface AssetListProps {
  assets: Asset[];
  onRemoveAsset: (id: string) => void;
  /** Maps upload status to a human-readable label. */
  getStatusLabel: (status: UploadStatus) => string;
  /** Retry upload for a failed asset. */
  onRetry?: (assetId: string) => void;
  selectedAssetIds?: string[];
  onToggleSelected?: (id: string) => void;
}

/** Colour and indicator for each upload status. */
function statusIndicator(
  status: UploadStatus,
): { dot: string; label: string } {
  switch (status) {
    case "idle":
      return { dot: "bg-gray-300", label: "text-gray-400" };
    case "compressing":
    case "requesting_ticket":
    case "uploading":
    case "finalizing":
      return { dot: "bg-amber-400", label: "text-amber-600" };
    case "done":
      return { dot: "bg-green-400", label: "text-green-600" };
    case "error":
      return { dot: "bg-red-400", label: "text-red-600" };
  }
}

export function AssetList({
  assets,
  onRemoveAsset,
  getStatusLabel,
  onRetry,
  selectedAssetIds = [],
  onToggleSelected,
}: AssetListProps) {
  return (
    <div className="p-2">
      {assets.map((asset) => {
        const { dot, label: labelCls } = statusIndicator(asset.uploadStatus);
        const isTerminal =
          asset.uploadStatus === "done" || asset.uploadStatus === "error";

        return (
          <div
            key={asset.id}
            className={`group flex items-center gap-2 rounded-xl p-2 transition-colors duration-studio ease-studio ${
              asset.uploadStatus === "error"
                ? "bg-red-50"
                : "hover:bg-surface"
            }`}
          >
            <div className="grid size-8 shrink-0 place-items-center rounded-[8px] bg-surface text-muted overflow-hidden">
              {asset.r2Url && asset.type === "image" ? (
                <img
                  src={asset.r2Url}
                  alt={asset.name}
                  className="size-full object-cover"
                  loading="lazy"
                />
              ) : asset.type === "file" ? (
                <FileIcon size={16} />
              ) : (
                <ImageIcon size={16} />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-block size-1.5 rounded-full ${dot}`}
                  aria-hidden="true"
                />
                <span className="truncate text-[13px] font-medium text-primary">
                  {asset.name}
                </span>
              </div>
              <div className={`truncate text-[11px] tracking-ui ${labelCls}`}>
                {getStatusLabel(asset.uploadStatus)}
                {asset.uploadStatus === "error" && " — try again"}
              </div>
            </div>
            <div className="flex items-center gap-1">
              {asset.uploadStatus === "done" && onToggleSelected && (
                <button
                  onClick={() => onToggleSelected(asset.id)}
                  className="rounded-full border border-border px-2 py-1 text-[10px] font-medium text-primary"
                  aria-pressed={selectedAssetIds.includes(asset.id)}
                  aria-label={`${selectedAssetIds.includes(asset.id) ? "Deselect" : "Select"} ${asset.name}`}
                >
                  {selectedAssetIds.includes(asset.id) ? "Selected" : "Select"}
                </button>
              )}
              {asset.uploadStatus === "error" && onRetry && (
                <button
                  onClick={() => onRetry(asset.id)}
                  className="flex size-6 items-center justify-center rounded-full text-muted opacity-0 transition-all duration-studio hover:bg-amber-100 hover:text-amber-600 focus-visible:opacity-100 group-hover:opacity-100"
                  aria-label={`Retry upload for ${asset.name}`}
                  title="Retry upload"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="23 4 23 10 17 10" />
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                  </svg>
                </button>
              )}
              <button
                onClick={() => onRemoveAsset(asset.id)}
                disabled={!isTerminal}
                className="flex size-6 items-center justify-center rounded-full text-muted opacity-0 transition-all duration-studio hover:bg-red-100 hover:text-red-500 focus-visible:opacity-100 group-hover:opacity-100 disabled:opacity-0"
                aria-label={`Remove ${asset.name}`}
              >
                <CloseIcon size={14} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
