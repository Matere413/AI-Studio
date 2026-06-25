import { useCallback, useRef, useState } from "react";
import type { Asset, StudioAction } from "@/app/studio-state";
import type { UploadStatus } from "@/app/studio-state";
import { AssetList } from "./AssetList";
import {
  validateFile,
  getStatusLabel,
  MAX_FILE_SIZE_BYTES,
} from "../assets-drawer-utils.ts";
import { useUpload } from "../../application/use-upload.ts";

// ─── Types ────────────────────────────────────────────────────

interface AssetsDrawerProps {
  assets: Asset[];
  isOpen: boolean;
  /** Reducer dispatch for state management. */
  dispatch: React.Dispatch<StudioAction>;
  /** Remove asset handler (called from AssetList). */
  onRemoveAsset: (id: string) => void;
  /** The project to upload assets into. Null disables upload functionality. */
  projectId: string | null;
}

// ─── Component ────────────────────────────────────────────────

export function AssetsDrawer({
  assets,
  isOpen,
  dispatch,
  onRemoveAsset,
  projectId,
}: AssetsDrawerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const { upload, retry, status: _hookStatus, error: _hookError, canRetry } =
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    useUpload({
      projectId: projectId ?? "",
      onStatusChange: (assetId, st) =>
        dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId, status: st }),
      onSuccess: (clientAssetId, serverAssetId, r2Url) => {
        // Mark the asset as done in local state
        dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId: clientAssetId, status: "done" });
        // Update the local asset ID to match the server-assigned ID
        if (serverAssetId !== clientAssetId) {
          dispatch({ type: "UPDATE_ASSET_SERVER_ID", oldId: clientAssetId, newId: serverAssetId });
        }
      },
      onError: (assetId, code, detail) => {
        dispatch({ type: "SET_ASSET_UPLOAD_STATUS", assetId, status: "error" });
      },
    });

  const handleRetry = useCallback(() => {
    void retry();
  }, [retry]);

  const handleUploadClick = useCallback(() => {
    if (!projectId) return; // disabled when no project
    setValidationError(null);
    fileInputRef.current?.click();
  }, [projectId]);

  const handleFileSelected = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Reset so the same file can be re-selected
      e.target.value = "";

      // Validate
      const validation = validateFile(file);
      if (!validation.valid) {
        setValidationError(validation.error);
        return;
      }

      setValidationError(null);

      // Create the asset in the store with initial idle status
      const assetId = crypto.randomUUID();
      dispatch({
        type: "ADD_SESSION_ASSET",
        asset: {
          id: assetId,
          name: file.name,
          r2Url: "",
          type: "image",
          uploadStatus: "idle",
          addedAt: new Date().toISOString(),
        },
      });

      // Start the upload pipeline
      await upload(assetId, file.name, file);
    },
    [dispatch, upload],
  );

  const currentUploadingId = (() => {
    // Find the first asset that is currently being uploaded
    const active = assets.find(
      (a) => a.uploadStatus !== "idle" && a.uploadStatus !== "done" && a.uploadStatus !== "error",
    );
    return active?.id ?? null;
  })();

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

      {validationError && (
        <div className="mx-2 mt-2 rounded-lg bg-red-50 px-3 py-2 text-[11px] text-red-600" role="alert">
          {validationError}
          <button
            onClick={() => setValidationError(null)}
            className="ml-2 font-medium underline"
            aria-label="Dismiss error"
          >
            Dismiss
          </button>
        </div>
      )}

      {assets.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-4">
          <p className="text-[12px] text-muted text-center">
            No assets yet. Upload an image or file to reference in your session.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <AssetList
            assets={assets}
            onRemoveAsset={onRemoveAsset}
            getStatusLabel={getStatusLabel}
            onRetry={handleRetry}
          />
        </div>
      )}

      {/* hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={["image/png", "image/jpeg"].join(",")}
        className="hidden"
        onChange={handleFileSelected}
        aria-label="Upload asset file"
      />

      {/* upload button */}
      <footer className="mt-auto border-t border-border p-4">
        <button
          onClick={handleUploadClick}
          disabled={currentUploadingId !== null || !projectId}
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-transparent px-3 text-[12px] font-medium tracking-ui text-primary transition-colors duration-studio ease-studio hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-highlight disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Upload asset file"
        >
          {!projectId
            ? "No Project"
            : currentUploadingId
              ? "Uploading…"
              : "+ Upload Asset"}
        </button>
      </footer>
    </aside>
  );
}
