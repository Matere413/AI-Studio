import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssetsDrawer } from "./AssetsDrawer";

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

  it("renders a collapsed toggle and expands the context asset panel", () => {
    render(
      <AssetsDrawer open={false} assets={[]} onToggle={() => {}} onAssetReady={() => {}} onRemove={() => {}} />
    );

    const toggle = screen.getByRole("button", { name: /toggle assets/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: /context assets/i })).not.toBeInTheDocument();
  });

  it("reads valid uploads as data URLs and guards files above 10MB", async () => {
    vi.stubGlobal("FileReader", MockFileReader);
    const onAssetReady = vi.fn();

    render(
      <AssetsDrawer open assets={[]} onToggle={() => {}} onAssetReady={onAssetReady} onRemove={() => {}} />
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
    const onRemove = vi.fn();

    render(
      <AssetsDrawer
        open
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
