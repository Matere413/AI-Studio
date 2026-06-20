import { beforeEach, describe, expect, it } from "vitest";
import { useUiStore } from "./uiStore";

function resetStore() {
  useUiStore.setState({
    assetsDrawerOpen: "open",
    isMobile: false,
  });
}

describe("uiStore", () => {
  beforeEach(() => {
    resetStore();
  });

  it("tracks the drawer tri-state and collapses on mobile", () => {
    expect(useUiStore.getState().assetsDrawerOpen).toBe("open");

    useUiStore.getState().toggleAssetsDrawer();
    expect(useUiStore.getState().assetsDrawerOpen).toBe("peek");

    useUiStore.getState().setMobile(true);
    expect(useUiStore.getState()).toEqual(
      expect.objectContaining({ isMobile: true, assetsDrawerOpen: "closed" })
    );

    useUiStore.getState().setMobile(false);
    expect(useUiStore.getState()).toEqual(
      expect.objectContaining({ isMobile: false, assetsDrawerOpen: "peek" })
    );
  });

  it("closes the drawer when escape is handled", () => {
    useUiStore.getState().openAssetsDrawer();
    useUiStore.getState().handleEscapeKey();

    expect(useUiStore.getState().assetsDrawerOpen).toBe("closed");
  });
});
