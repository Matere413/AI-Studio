"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MOCK_MESSAGES, MOCK_ASSETS } from "@/shared/presentation/mock-data";
import { ChatSidebar } from "@/features/chat/presentation/components/ChatSidebar";
import { StudioTopBar } from "@/features/studio/presentation/components/StudioTopBar";
import { StudioCanvas } from "@/features/studio/presentation/components/StudioCanvas";
import { AssetsDrawer } from "@/features/assets/presentation/components/AssetsDrawer";

const BREAKPOINT_LG = 1024;

export default function HomePage() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const userToggled = useRef(false);

  /* Responsive default: collapsed on small viewports, open on >=1024px.
     Tracks resize crossing both ways — opens when crossing from <1024 to
     >=1024, closes when crossing from >=1024 to <1024. Respects user's
     explicit toggle: once the user manually toggles, resize auto-adjust
     stops until next page load. Runs once after mount to avoid hydration
     mismatch — SSR always renders collapsed. */
  useEffect(() => {
    let prevWidth = window.innerWidth;

    function handleResize() {
      const currentWidth = window.innerWidth;
      const crossedUp = prevWidth < BREAKPOINT_LG && currentWidth >= BREAKPOINT_LG;
      const crossedDown = prevWidth >= BREAKPOINT_LG && currentWidth < BREAKPOINT_LG;

      if (!userToggled.current) {
        if (crossedUp) setDrawerOpen(true);
        if (crossedDown) setDrawerOpen(false);
      }

      prevWidth = currentWidth;
    }

    if (window.innerWidth >= BREAKPOINT_LG) {
      setDrawerOpen(true);
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const toggleDrawer = useCallback(() => {
    userToggled.current = true;
    setDrawerOpen((prev) => !prev);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-base">
      <ChatSidebar messages={MOCK_MESSAGES} />

      <main className="flex min-w-0 flex-1 flex-col bg-base">
        <StudioTopBar
          onToggleAssets={toggleDrawer}
          assetsExpanded={drawerOpen}
        />

        <div className="flex min-h-0 flex-1 overflow-hidden">
          <StudioCanvas />
          <AssetsDrawer assets={MOCK_ASSETS} isOpen={drawerOpen} />
        </div>
      </main>
    </div>
  );
}
