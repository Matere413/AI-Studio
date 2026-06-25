// ─── Unit Tests: pickEditingAssetId ───────────────────────────────
// Tests the pure selector that decides whether to send an R2-backed
// `image_asset_id` (preferred) or fall back to legacy `image_base64`
// for the flux2_editing workflow.
//
// Bug being fixed (Base64 Ghost): the previous inline logic in page.tsx
// gated the asset_id path on `a.r2Url`, but the reducer never stores
// `r2Url` (UPDATE_ASSET_SERVER_ID only updates `id`). So the gate was
// always false and the client ALWAYS fell back to base64 even after a
// successful R2 upload. The correct gate is `uploadStatus === "done"`:
// once the upload finalizes, the asset's `id` IS the server-assigned
// asset_id (via UPDATE_ASSET_SERVER_ID).

import { describe, it } from "node:test";
import assert from "node:assert";
import { pickEditingAssetId } from "../pick-editing-asset.ts";
import type { Asset } from "../../../../app/studio-state.ts";

function makeAsset(overrides: Partial<Asset> & { id: string }): Asset {
  return {
    name: "ref.png",
    r2Url: "",
    type: "image",
    uploadStatus: "idle",
    addedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

void describe("pickEditingAssetId", () => {
  void it("returns the asset id for a done image asset with empty r2Url", () => {
    // RED under the old inline logic: `a.r2Url` was falsy so the asset
    // was never selected and base64 was always used.
    const assets: Asset[] = [
      makeAsset({ id: "server-asset-1", uploadStatus: "done", r2Url: "" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), "server-asset-1");
  });

  void it("returns undefined when no asset is done yet", () => {
    const assets: Asset[] = [
      makeAsset({ id: "client-uuid-1", uploadStatus: "uploading" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), undefined);
  });

  void it("returns undefined for an empty asset list", () => {
    assert.strictEqual(pickEditingAssetId([]), undefined);
  });

  void it("ignores non-image assets even when done", () => {
    const assets: Asset[] = [
      makeAsset({ id: "file-1", type: "file", uploadStatus: "done" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), undefined);
  });

  void it("still works when r2Url happens to be populated", () => {
    const assets: Asset[] = [
      makeAsset({ id: "asset-2", uploadStatus: "done", r2Url: "https://r2/x" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), "asset-2");
  });

  void it("prefers a done asset over idle assets", () => {
    const assets: Asset[] = [
      makeAsset({ id: "idle-1", uploadStatus: "idle" }),
      makeAsset({ id: "done-1", uploadStatus: "done" }),
      makeAsset({ id: "idle-2", uploadStatus: "idle" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), "done-1");
  });

  void it("selects the first done image asset when multiple are done", () => {
    const assets: Asset[] = [
      makeAsset({ id: "done-a", uploadStatus: "done" }),
      makeAsset({ id: "done-b", uploadStatus: "done" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), "done-a");
  });

  void it("does not select an asset in the error state", () => {
    const assets: Asset[] = [
      makeAsset({ id: "err-1", uploadStatus: "error" }),
    ];
    assert.strictEqual(pickEditingAssetId(assets), undefined);
  });
});
