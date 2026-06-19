"use client";

import { X } from "lucide-react";
import type { AssetItem } from "../AssetsDrawer";
import { IconButton } from "./IconButton";
import styles from "./FileThumb.module.css";

interface FileThumbProps {
  asset: AssetItem;
  onRemove: (id: string) => void;
}

export function FileThumb({ asset, onRemove }: FileThumbProps) {
  return (
    <article className={styles.thumb}>
      <img alt="" className={styles.preview} src={asset.url} />

      <div className={styles.meta}>
        <div>
          <p className={styles.name}>{asset.name}</p>
          <p className={`text-mono ${styles.caption}`}>Reference asset</p>
        </div>

        <IconButton label={`Remove ${asset.name}`} onClick={() => onRemove(asset.id)}>
          <X aria-hidden="true" />
        </IconButton>
      </div>
    </article>
  );
}
