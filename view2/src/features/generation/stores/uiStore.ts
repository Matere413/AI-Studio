import { create } from "zustand";

export type DrawerState = "open" | "peek" | "closed";

interface UiStore {
  assetsDrawerOpen: DrawerState;
  isMobile: boolean;
  setMobile(isMobile: boolean): void;
  setAssetsDrawerOpen(state: DrawerState): void;
  toggleAssetsDrawer(): void;
  openAssetsDrawer(): void;
  closeAssetsDrawer(): void;
  handleEscapeKey(): void;
}

export const useUiStore = create<UiStore>((set, get) => ({
  assetsDrawerOpen: "open",
  isMobile: false,

  setMobile(isMobile) {
    set((state) => ({
      isMobile,
      assetsDrawerOpen: isMobile
        ? "closed"
        : state.assetsDrawerOpen === "closed"
          ? "peek"
          : state.assetsDrawerOpen,
    }));
  },

  setAssetsDrawerOpen(state) {
    set({ assetsDrawerOpen: state });
  },

  toggleAssetsDrawer() {
    const state = get().assetsDrawerOpen;

    set({
      assetsDrawerOpen:
        state === "open" ? "peek" : state === "peek" ? "open" : "open",
    });
  },

  openAssetsDrawer() {
    set({ assetsDrawerOpen: "open" });
  },

  closeAssetsDrawer() {
    set({ assetsDrawerOpen: "closed" });
  },

  handleEscapeKey() {
    set({ assetsDrawerOpen: "closed" });
  },
}));
