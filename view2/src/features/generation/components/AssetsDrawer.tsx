"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import FileThumb from "@/shared/components/ui/FileThumb";
import IconButton from "@/shared/components/ui/IconButton";
import { useGenerationStore } from "../stores/generationStore";
import { useUiStore } from "../stores/uiStore";
import styles from "./GenerationStudio.module.css";

const MAX_REFERENCE_BYTES = 10 * 1024 * 1024;
const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type DrawerAsset = {
  name: string;
  url: string;
};

export default function AssetsDrawer() {
  const isMobile = useUiStore((state) => state.isMobile);
  const assetsDrawerOpen = useUiStore((state) => state.assetsDrawerOpen);
  const setAssetsDrawerOpen = useUiStore((state) => state.setAssetsDrawerOpen);
  const handleEscapeKey = useUiStore((state) => state.handleEscapeKey);
  const referenceGallery = useGenerationStore((state) => state.referenceGallery);
  const setReferenceFaceUrl = useGenerationStore((state) => state.setReferenceFaceUrl);
  const addToGallery = useGenerationStore((state) => state.addToGallery);
  const removeFromGallery = useGenerationStore((state) => state.removeFromGallery);
  const [assets, setAssets] = useState(() =>
    referenceGallery.map((url, index) => ({ name: `Reference ${index + 1}`, url }))
  );
  const hydrated = useRef(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusOnCloseRef = useRef(false);

  const getFocusableElements = (container: HTMLElement | null) => {
    if (!container) {
      return [] as HTMLElement[];
    }

    return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
  };

  const openDrawer = useCallback(
    (trigger: HTMLButtonElement) => {
      triggerRef.current = trigger;
      restoreFocusOnCloseRef.current = true;
      setAssetsDrawerOpen("open");
    },
    [setAssetsDrawerOpen]
  );

  const closeDrawer = useCallback(() => {
    restoreFocusOnCloseRef.current = true;
    handleEscapeKey();
  }, [handleEscapeKey]);

  const isDrawerVisible = isMobile && assetsDrawerOpen !== "closed";

  useEffect(() => {
    if (hydrated.current) {
      return;
    }

    if (referenceGallery.length > 0) {
      setAssets(referenceGallery.map((url, index) => ({ name: `Reference ${index + 1}`, url })));
    }

    hydrated.current = true;
  }, [referenceGallery]);

  useEffect(() => {
    if (!isDrawerVisible) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDrawer();
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusables = getFocusableElements(panelRef.current);

      if (focusables.length === 0) {
        return;
      }

      const activeElement = document.activeElement;
      const currentIndex = focusables.indexOf(activeElement as HTMLElement);
      let nextIndex = 0;

      if (event.shiftKey) {
        nextIndex = currentIndex <= 0 ? focusables.length - 1 : currentIndex - 1;
      } else if (currentIndex !== -1 && currentIndex !== focusables.length - 1) {
        nextIndex = currentIndex + 1;
      }

      event.preventDefault();
      focusables[nextIndex]?.focus();
    };

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [closeDrawer, isDrawerVisible]);

  useEffect(() => {
    if (!isDrawerVisible) {
      return;
    }

    getFocusableElements(panelRef.current)[0]?.focus();
  }, [isDrawerVisible]);

  useEffect(() => {
    if (!isMobile || assetsDrawerOpen !== "closed" || !restoreFocusOnCloseRef.current) {
      return;
    }

    triggerRef.current?.focus();
    restoreFocusOnCloseRef.current = false;
  }, [assetsDrawerOpen, isMobile]);

  const handleUpload = (files: FileList | null) => {
    if (!files) return;

    Array.from(files).forEach((file) => {
      if (!/^image\/(png|jpeg)$/.test(file.type) || file.size > MAX_REFERENCE_BYTES) {
        return;
      }

      const reader = new FileReader();
      reader.onload = () => {
        const url = String(reader.result ?? "");
        const nextAsset = { name: file.name, url };

        setAssets((current) => [nextAsset, ...current]);
        setReferenceFaceUrl(url);
        addToGallery(url);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeAsset = (asset: DrawerAsset) => {
    setAssets((current) => current.filter((item) => item.url !== asset.url));
    removeFromGallery(asset.url);
  };

  if (isMobile && assetsDrawerOpen === "closed") {
    return (
      <IconButton
        aria-controls="view2-context-assets"
        aria-expanded={assetsDrawerOpen !== "closed"}
        aria-label="Open context assets"
        onClick={(event) => openDrawer(event.currentTarget)}
        ref={triggerRef}
      >
        ⊕
      </IconButton>
    );
  }

  const panel = (
    <aside
      className={styles.panel}
      aria-label="Context assets"
      id="view2-context-assets"
      role={isMobile ? "dialog" : "complementary"}
      aria-modal={isMobile ? "true" : undefined}
      ref={panelRef}
    >
      <header className={styles.panelHeader}>
        <div>
          <p className={styles.panelEyebrow}>Context assets</p>
          <h2 className={styles.panelTitle}>Context assets</h2>
        </div>

        {isMobile ? (
          <IconButton aria-label="Close context assets" onClick={closeDrawer}>
            ×
          </IconButton>
        ) : null}
      </header>

      <label className={styles.uploadField}>
        <span>Upload reference image</span>
        <input
          aria-label="Upload reference image"
          accept="image/png,image/jpeg"
          multiple
          type="file"
          onChange={(event) => handleUpload(event.target.files)}
        />
      </label>

      <ul className={styles.drawerList} aria-label="Reference gallery">
        {assets.map((asset) => (
          <li key={asset.url} className={styles.drawerItem}>
            <FileThumb name={asset.name} url={asset.url} />
            <button
              className={styles.drawerRemove}
              onClick={() => removeAsset(asset)}
              type="button"
            >
              Remove {asset.name}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );

  if (isMobile) {
    return (
      <div className={styles.drawerOverlay}>
        {panel}
      </div>
    );
  }

  return panel;
}
