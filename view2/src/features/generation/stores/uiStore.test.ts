import { describe, expect, it } from "vitest";
import { useUiStore } from "./uiStore";

describe("uiStore", () => {
  it("defaults to auto drawer visibility and square aspect ratio", () => {
    expect(useUiStore.getState().assetsDrawerOpen).toBe("auto");
    expect(useUiStore.getState().aspectRatio).toBe("1:1");
  });

  it("supports explicit drawer and aspect ratio setters", () => {
    useUiStore.getState().setAssetsDrawer(true);
    expect(useUiStore.getState().assetsDrawerOpen).toBe(true);

    useUiStore.getState().setAssetsDrawer(false);
    expect(useUiStore.getState().assetsDrawerOpen).toBe(false);

    useUiStore.getState().setAspectRatio("16:9");
    expect(useUiStore.getState().aspectRatio).toBe("16:9");
  });

  it("toggles the assets drawer from auto into an explicit boolean", () => {
    useUiStore.getState().setAssetsDrawer("auto");
    useUiStore.getState().toggleAssetsDrawer();

    expect(useUiStore.getState().assetsDrawerOpen).toBe(true);

    useUiStore.getState().toggleAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe(false);
  });
});
