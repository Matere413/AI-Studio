"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { FileThumb } from "./primitives/FileThumb";
import styles from "./AssetsDrawer.module.css";

const MAX_ASSET_SIZE_BYTES = 10 * 1024 * 1024;

export interface AssetItem {
  id: string;
  url: string;
  name: string;
}

interface AssetsDrawerProps {
  isOpen: boolean;
  assets: AssetItem[];
  onToggle: () => void;
  onAssetReady: (dataUrl: string, file: File) => void;
  onRemove: (id: string) => void;
}

export function AssetsDrawer({
  isOpen,
  assets,
  onToggle,
  onAssetReady,
  onRemove,
}: AssetsDrawerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const isDesktop = useMediaQuery(1024);

  useEffect(() => {
    if (!isOpen || isDesktop) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onToggle();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isDesktop, isOpen, onToggle]);

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
          aria-expanded={isOpen}
          aria-label="Toggle assets"
          className={`btn btn-ghost ${styles.toggleButton}`}
          onClick={onToggle}
          type="button"
        >
          Assets
        </button>
      </div>

      {!isDesktop && isOpen ? (
        <div className={styles.backdrop} aria-hidden="true" onClick={onToggle} />
      ) : null}

      {isOpen ? (
        <aside
          aria-label="Context Assets"
          className={styles.drawer}
          data-overlay={isDesktop ? undefined : "true"}
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
              assets.map((asset) => <FileThumb asset={asset} key={asset.id} onRemove={onRemove} />)
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
