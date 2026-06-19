import { beforeEach, describe, expect, it } from "vitest";
import { useUiStore } from "./uiStore";

describe("uiStore", () => {
  beforeEach(() => {
    useUiStore.getState().closeAssetsDrawer();
  });

  it("toggles the assets drawer open and closed", () => {
    expect(useUiStore.getState().assetsDrawerOpen).toBe(false);

    useUiStore.getState().toggleAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe(true);

    useUiStore.getState().toggleAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe(false);
  });

  it("supports explicit drawer actions", () => {
    useUiStore.getState().openAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe(true);

    useUiStore.getState().closeAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe(false);
  });
});
