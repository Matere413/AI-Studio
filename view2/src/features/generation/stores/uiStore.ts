import { create } from "zustand";

export type DrawerVisibility = "auto" | boolean;
export type AspectRatio = "1:1" | "16:9" | "9:16";

interface UiStoreState {
  assetsDrawerOpen: DrawerVisibility;
  aspectRatio: AspectRatio;
  openAssetsDrawer(): void;
  closeAssetsDrawer(): void;
  toggleAssetsDrawer(): void;
  setAssetsDrawer(value: DrawerVisibility): void;
  setAspectRatio(value: AspectRatio): void;
}

export const useUiStore = create<UiStoreState>((set) => ({
  assetsDrawerOpen: "auto",
  aspectRatio: "1:1",
  openAssetsDrawer: () => set({ assetsDrawerOpen: true }),
  closeAssetsDrawer: () => set({ assetsDrawerOpen: false }),
  toggleAssetsDrawer: () =>
    set((state) => ({
      assetsDrawerOpen:
        state.assetsDrawerOpen === "auto" ? true : !state.assetsDrawerOpen,
    })),
  setAssetsDrawer: (value) => set({ assetsDrawerOpen: value }),
  setAspectRatio: (value) => set({ aspectRatio: value }),
}));
