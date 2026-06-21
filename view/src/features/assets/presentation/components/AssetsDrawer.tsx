import { useCallback, useRef } from "react";
import type { Asset } from "@/app/studio-state";
import { AssetList } from "./AssetList";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

interface AssetsDrawerProps {
  assets: Asset[];
  isOpen: boolean;
  onUploadAsset: (asset: Asset) => void;
  onRemoveAsset: (id: string) => void;
}

export function AssetsDrawer({ assets, isOpen, onUploadAsset, onRemoveAsset }: AssetsDrawerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileSelected = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Enforce max 10MB
      if (file.size > MAX_FILE_SIZE_BYTES) {
        window.alert(`File too large. Maximum size is ${MAX_FILE_SIZE_BYTES / (1024 * 1024)} MB.`);
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        onUploadAsset({
          id: crypto.randomUUID(),
          name: file.name,
          dataUrl,
          type: file.type.startsWith("image/") ? "image" : "file",
          addedAt: new Date().toISOString(),
        });
      };
      reader.onerror = () => {
        window.alert("Failed to read the selected file.");
      };
      reader.readAsDataURL(file);

      // Reset so the same file can be re-selected
      e.target.value = "";
    },
    [onUploadAsset],
  );

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

      {assets.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-4">
          <p className="text-[12px] text-muted text-center">
            No assets yet. Upload an image or file to reference in your session.
          </p>
        </div>
      ) : (
        <AssetList assets={assets} onRemoveAsset={onRemoveAsset} />
      )}

      {/* hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={handleFileSelected}
        aria-label="Upload asset file"
      />

      {/* upload button */}
      <footer className="mt-auto border-t border-border p-4">
        <button
          onClick={handleUploadClick}
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight"
        >
          + Upload Asset
        </button>
      </footer>
    </aside>
  );
}
