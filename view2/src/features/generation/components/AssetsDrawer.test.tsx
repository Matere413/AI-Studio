import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssetsDrawer } from "./AssetsDrawer";

function createMatchMedia(matches: boolean) {
  return vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

class MockFileReader {
  result: string | ArrayBuffer | null = null;
  onload: null | (() => void) = null;

  readAsDataURL(file: File) {
    this.result = `data:${file.type};base64,ZmFrZQ==`;
    this.onload?.();
  }
}

describe("AssetsDrawer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders an inline drawer with FileThumb rows on desktop", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));

    render(
      <AssetsDrawer
        assets={[{ id: "asset-1", url: "data:image/png;base64,aaa", name: "product.png" }]}
        isOpen
        onAssetReady={() => {}}
        onRemove={() => {}}
        onToggle={() => {}}
      />
    );

    expect(screen.getByRole("complementary", { name: /context assets/i })).toBeInTheDocument();
    expect(screen.getByText("product.png")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /remove product.png/i })).toBeInTheDocument();
  });

  it("renders a fixed overlay on mobile and closes on escape", async () => {
    vi.stubGlobal("matchMedia", createMatchMedia(false));
    const onToggle = vi.fn();

    render(
      <AssetsDrawer
        assets={[]}
        isOpen
        onAssetReady={() => {}}
        onRemove={() => {}}
        onToggle={onToggle}
      />
    );

    expect(screen.getByRole("complementary", { name: /context assets/i })).toHaveAttribute(
      "data-overlay",
      "true",
    );

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("reads valid uploads as data URLs and guards files above 10MB", async () => {
    vi.stubGlobal("FileReader", MockFileReader);
    vi.stubGlobal("matchMedia", createMatchMedia(true));
    const onAssetReady = vi.fn();

    render(
      <AssetsDrawer
        assets={[]}
        isOpen
        onAssetReady={onAssetReady}
        onRemove={() => {}}
        onToggle={() => {}}
      />
    );

    const input = screen.getByLabelText(/upload reference asset/i);
    const validFile = new File(["reference"], "reference.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [validFile] } });

    await waitFor(() => {
      expect(onAssetReady).toHaveBeenCalledWith(
        "data:image/png;base64,ZmFrZQ==",
        validFile
      );
    });

    const oversized = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "huge.png", {
      type: "image/png",
    });
    fireEvent.change(input, { target: { files: [oversized] } });

    expect(screen.getByRole("alert")).toHaveTextContent("10MB");
    expect(onAssetReady).toHaveBeenCalledTimes(1);
  });

  it("renders gallery assets and removes them", () => {
    vi.stubGlobal("matchMedia", createMatchMedia(true));
    const onRemove = vi.fn();

    render(
      <AssetsDrawer
        isOpen
        assets={[{ id: "asset-1", url: "data:image/png;base64,aaa", name: "product.png" }]}
        onToggle={() => {}}
        onAssetReady={() => {}}
        onRemove={onRemove}
      />
    );

    expect(screen.getByText("product.png")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /remove product.png/i }));

    expect(onRemove).toHaveBeenCalledWith("asset-1");
  });
});
