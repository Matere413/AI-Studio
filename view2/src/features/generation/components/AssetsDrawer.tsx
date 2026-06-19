"use client";

import { useRef, useState, type ChangeEvent } from "react";
import styles from "./AssetsDrawer.module.css";

const MAX_ASSET_SIZE_BYTES = 10 * 1024 * 1024;

export interface AssetItem {
  id: string;
  url: string;
  name: string;
}

interface AssetsDrawerProps {
  open: boolean;
  assets: AssetItem[];
  onToggle: () => void;
  onAssetReady: (dataUrl: string, file: File) => void;
  onRemove: (id: string) => void;
}

export function AssetsDrawer({
  open,
  assets,
  onToggle,
  onAssetReady,
  onRemove,
}: AssetsDrawerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_ASSET_SIZE_BYTES) {
      setError("Reference assets must be 10MB or less");
      event.target.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setError(null);
        onAssetReady(reader.result, file);
      }
    };
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  return (
    <div className={styles.root}>
      <div className={styles.toggleRail}>
        <button
          aria-controls="assets-drawer"
          aria-expanded={open}
          aria-label="Toggle assets"
          className={`btn btn-ghost ${styles.toggleButton}`}
          onClick={onToggle}
          type="button"
        >
          Assets
        </button>
      </div>

      {open ? (
        <aside
          aria-label="Context Assets"
          className={styles.drawer}
          id="assets-drawer"
        >
          <header className={styles.header}>
            <h2 className={styles.title}>Context Assets</h2>
            <p className={styles.description}>Reference files for the selected workflow.</p>
          </header>

          <div className={styles.gallery}>
            {assets.length === 0 ? (
              <p className={styles.empty}>No assets attached yet.</p>
            ) : (
              assets.map((asset) => (
                <div className={styles.asset} key={asset.id}>
                  <img alt="" className={styles.thumb} src={asset.url} />
                  <span className={styles.assetName}>{asset.name}</span>
                  <button
                    aria-label={`Remove ${asset.name}`}
                    className={`btn btn-ghost ${styles.removeButton}`}
                    onClick={() => onRemove(asset.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              ))
            )}
          </div>

          <footer className={styles.footer}>
            <input
              accept="image/*"
              aria-label="Upload reference asset"
              className={styles.fileInput}
              onChange={handleFileChange}
              ref={inputRef}
              type="file"
            />
            <p className={`text-mono ${styles.limit}`}>10MB limit per file</p>
            {error ? (
              <p className={styles.error} role="alert">
                {error}
              </p>
            ) : null}
          </footer>
        </aside>
      ) : null}
    </div>
  );
}
