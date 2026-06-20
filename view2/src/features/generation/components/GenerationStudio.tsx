"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import AssetsDrawer from "./AssetsDrawer";
import ChatSidebar from "./ChatSidebar";
import EventTerminal from "./EventTerminal";
import OutputCanvas from "./OutputCanvas";
import SessionHistory from "./SessionHistory";
import TopAppBar from "./TopAppBar";
import styles from "./GenerationStudio.module.css";
import { useUiStore } from "../stores/uiStore";
import {
  STUDIO_ASSETS_COLUMN_DESKTOP,
  STUDIO_ASSETS_COLUMN_MOBILE,
  STUDIO_CHAT_COLUMN_DESKTOP,
  STUDIO_CHAT_COLUMN_MOBILE,
  STUDIO_DESKTOP_MEDIA_QUERY,
} from "../layout";

export function resolveStudioLayout(isMounted: boolean, isDesktop: boolean) {
  return isMounted && isDesktop ? "desktop" : "mobile";
}

export default function GenerationStudio() {
  const isDesktop = useMediaQuery(STUDIO_DESKTOP_MEDIA_QUERY);
  const [isMounted, setIsMounted] = useState(false);
  const setMobile = useUiStore((state) => state.setMobile);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const layout = resolveStudioLayout(isMounted, isDesktop);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    setMobile(layout !== "desktop");
  }, [isMounted, layout, setMobile]);

  const shellStyle: CSSProperties = {
    "--view2-chat-column": layout === "desktop" ? STUDIO_CHAT_COLUMN_DESKTOP : STUDIO_CHAT_COLUMN_MOBILE,
    "--view2-assets-column": layout === "desktop"
      ? STUDIO_ASSETS_COLUMN_DESKTOP
      : STUDIO_ASSETS_COLUMN_MOBILE,
  } as CSSProperties;

  return (
    <main
      className={styles.shell}
      aria-label="View2 studio shell"
      data-layout={layout}
      style={shellStyle}
    >
      <div className={styles.chatPane}>
        <ChatSidebar />
      </div>

      <section className={styles.workspacePane} aria-label="Workspace canvas">
        <TopAppBar />
        <OutputCanvas />
        <EventTerminal />
        <SessionHistory />
      </section>

      <div className={styles.assetsPane}>
        <AssetsDrawer />
      </div>
    </main>
  );
}
