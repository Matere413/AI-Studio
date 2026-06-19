import { create } from "zustand";

interface UiStoreState {
  assetsDrawerOpen: boolean;
  openAssetsDrawer(): void;
  closeAssetsDrawer(): void;
  toggleAssetsDrawer(): void;
}

export const useUiStore = create<UiStoreState>((set) => ({
  assetsDrawerOpen: false,
  openAssetsDrawer: () => set({ assetsDrawerOpen: true }),
  closeAssetsDrawer: () => set({ assetsDrawerOpen: false }),
  toggleAssetsDrawer: () =>
    set((state) => ({ assetsDrawerOpen: !state.assetsDrawerOpen })),
}));
