// ─── Unit Tests: Assets Reducer ─────────────────────────────────
// Tests the new asset store contract: no `dataUrl`, `r2Url` and
// `uploadStatus` fields, and upload status state transitions.
//
// These tests will FAIL initially (RED) until studio-state.ts is
// updated with the new Asset shape and actions (GREEN).

import { describe, it } from "node:test";
import assert from "node:assert";
import {
  studioReducer,
  initialStudioState,
} from "../../../app/studio-state.ts";
import type { Asset, StudioState } from "../../../app/studio-state.ts";

void describe("studioReducer — asset store contract", () => {
  // ── Asset shape: NO dataUrl ───────────────────────────────

  void it("Asset has NO dataUrl field after ADD_SESSION_ASSET", () => {
    const asset: Asset = {
      id: "a1",
      name: "test.webp",
      type: "image",
      r2Url: "https://r2.example.com/test.webp",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    // The spread should NOT leak any dataUrl — this fails if
    // dataUrl is still present on the Asset type
    assert.strictEqual("dataUrl" in asset, false);
  });

  void it("Asset has r2Url field after ADD_SESSION_ASSET", () => {
    const asset: Asset = {
      id: "a2",
      name: "asset.webp",
      type: "image",
      r2Url: "https://r2.example.com/asset.webp",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const result = studioReducer(initialStudioState, {
      type: "ADD_SESSION_ASSET",
      asset,
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(
      result.sessionAssets[0].r2Url,
      "https://r2.example.com/asset.webp",
    );
  });

  void it("Asset has uploadStatus field initialized to idle", () => {
    const asset: Asset = {
      id: "a3",
      name: "init.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const result = studioReducer(initialStudioState, {
      type: "ADD_SESSION_ASSET",
      asset,
    });
    assert.strictEqual(result.sessionAssets[0].uploadStatus, "idle");
  });

  // ── Upload status transitions ─────────────────────────────

  void it("SET_ASSET_UPLOAD_STATUS transitions from idle to compressing", () => {
    const asset: Asset = {
      id: "a-u1",
      name: "up.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "SET_ASSET_UPLOAD_STATUS",
      assetId: "a-u1",
      status: "compressing",
    });
    const updated = result.sessionAssets.find((a) => a.id === "a-u1");
    assert.ok(updated, "Asset must still exist");
    assert.strictEqual(updated!.uploadStatus, "compressing");
  });

  void it("SET_ASSET_UPLOAD_STATUS transitions to done", () => {
    const asset: Asset = {
      id: "a-u2",
      name: "done.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "uploading",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "SET_ASSET_UPLOAD_STATUS",
      assetId: "a-u2",
      status: "done",
    });
    const updated = result.sessionAssets.find((a) => a.id === "a-u2");
    assert.strictEqual(updated!.uploadStatus, "done");
  });

  void it("SET_ASSET_UPLOAD_STATUS transitions to error", () => {
    const asset: Asset = {
      id: "a-u3",
      name: "fail.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "uploading",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "SET_ASSET_UPLOAD_STATUS",
      assetId: "a-u3",
      status: "error",
    });
    const updated = result.sessionAssets.find((a) => a.id === "a-u3");
    assert.strictEqual(updated!.uploadStatus, "error");
  });

  void it("SET_ASSET_UPLOAD_STATUS preserves other asset fields", () => {
    const asset: Asset = {
      id: "a-u4",
      name: "preserve.webp",
      type: "image",
      r2Url: "https://r2.example.com/preserve.webp",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "SET_ASSET_UPLOAD_STATUS",
      assetId: "a-u4",
      status: "done",
    });
    const updated = result.sessionAssets.find((a) => a.id === "a-u4");
    assert.strictEqual(updated!.name, "preserve.webp");
    assert.strictEqual(
      updated!.r2Url,
      "https://r2.example.com/preserve.webp",
    );
    assert.strictEqual(updated!.type, "image");
  });

  void it("SET_ASSET_UPLOAD_STATUS does nothing for unknown assetId", () => {
    const asset: Asset = {
      id: "a-u5",
      name: "only.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "SET_ASSET_UPLOAD_STATUS",
      assetId: "nonexistent",
      status: "done",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].uploadStatus, "idle");
  });

  // ── ADD_SESSION_ASSET with new Asset shape ─────────────────

  void it("ADD_SESSION_ASSET accepts asset without dataUrl", () => {
    const asset: Asset = {
      id: "a-add1",
      name: "no-dataurl.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const result = studioReducer(initialStudioState, {
      type: "ADD_SESSION_ASSET",
      asset,
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].name, "no-dataurl.webp");
    // Verify dataUrl is NOT part of the stored asset
    assert.strictEqual("dataUrl" in result.sessionAssets[0], false);
  });

  void it("ADD_SESSION_ASSET preserves existing sessionAssets with new shape", () => {
    const existing: Asset = {
      id: "a-old",
      name: "old.webp",
      type: "image",
      r2Url: "https://r2.example.com/old.webp",
      uploadStatus: "done",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [existing],
    };
    const newAsset: Asset = {
      id: "a-new",
      name: "new.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:01Z",
    };
    const result = studioReducer(state, {
      type: "ADD_SESSION_ASSET",
      asset: newAsset,
    });
    assert.strictEqual(result.sessionAssets.length, 2);
    assert.strictEqual(result.sessionAssets[0].id, "a-old");
    assert.strictEqual(result.sessionAssets[0].r2Url, "https://r2.example.com/old.webp");
    assert.strictEqual(result.sessionAssets[0].uploadStatus, "done");
    assert.strictEqual(result.sessionAssets[1].id, "a-new");
    assert.strictEqual(result.sessionAssets[1].uploadStatus, "idle");
  });

  // ── UPDATE_ASSET_SERVER_ID ──────────────────────────────────

  void it("UPDATE_ASSET_SERVER_ID replaces asset id from old to new", () => {
    const asset: Asset = {
      id: "client-uuid",
      name: "test.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "done",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "UPDATE_ASSET_SERVER_ID",
      oldId: "client-uuid",
      newId: "server-asset-123",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].id, "server-asset-123");
    assert.strictEqual(result.sessionAssets[0].name, "test.webp"); // other fields preserved
    assert.strictEqual(result.sessionAssets[0].uploadStatus, "done");
  });

  void it("UPDATE_ASSET_SERVER_ID stores r2Url when provided", () => {
    const asset: Asset = {
      id: "client-uuid",
      name: "thumb.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "done",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "UPDATE_ASSET_SERVER_ID",
      oldId: "client-uuid",
      newId: "server-asset-456",
      r2Url: "https://r2.example.com/projects/p1/thumb.webp",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].id, "server-asset-456");
    assert.strictEqual(
      result.sessionAssets[0].r2Url,
      "https://r2.example.com/projects/p1/thumb.webp",
    );
  });

  void it("UPDATE_ASSET_SERVER_ID without r2Url preserves existing r2Url", () => {
    const asset: Asset = {
      id: "existing-id",
      name: "test.webp",
      type: "image",
      r2Url: "https://r2.example.com/existing.webp",
      uploadStatus: "done",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "UPDATE_ASSET_SERVER_ID",
      oldId: "existing-id",
      newId: "new-id",
      // no r2Url — should preserve the existing one
    });
    assert.strictEqual(result.sessionAssets[0].id, "new-id");
    assert.strictEqual(
      result.sessionAssets[0].r2Url,
      "https://r2.example.com/existing.webp",
    );
  });

  void it("UPDATE_ASSET_SERVER_ID does nothing when oldId not found", () => {
    const asset: Asset = {
      id: "existing-id",
      name: "test.webp",
      type: "image",
      r2Url: "",
      uploadStatus: "idle",
      addedAt: "2026-06-25T00:00:00Z",
    };
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [asset],
    };
    const result = studioReducer(state, {
      type: "UPDATE_ASSET_SERVER_ID",
      oldId: "nonexistent",
      newId: "server-asset-999",
    });
    assert.strictEqual(result.sessionAssets.length, 1);
    assert.strictEqual(result.sessionAssets[0].id, "existing-id");
  });

  void it("tracks explicitly selected assets separately from uploaded assets", () => {
    const state: StudioState = {
      ...initialStudioState,
      sessionAssets: [
        { id: "done-1", name: "one.webp", type: "image", r2Url: "", uploadStatus: "done", addedAt: "2026-06-25T00:00:00Z" },
        { id: "done-2", name: "two.webp", type: "image", r2Url: "", uploadStatus: "done", addedAt: "2026-06-25T00:00:01Z" },
      ],
    };

    const result = studioReducer(state, { type: "TOGGLE_SELECTED_ASSET", id: "done-2" });

    assert.deepStrictEqual(result.selectedAssetIds, ["done-2"]);
  });

  void it("removes deleted assets from the explicit selection", () => {
    const state: StudioState = {
      ...initialStudioState,
      selectedAssetIds: ["keep", "remove"],
      sessionAssets: [
        { id: "keep", name: "keep.webp", type: "image", r2Url: "", uploadStatus: "done", addedAt: "2026-06-25T00:00:00Z" },
        { id: "remove", name: "remove.webp", type: "image", r2Url: "", uploadStatus: "done", addedAt: "2026-06-25T00:00:01Z" },
      ],
    };

    const result = studioReducer(state, { type: "REMOVE_SESSION_ASSET", id: "remove" });

    assert.deepStrictEqual(result.selectedAssetIds, ["keep"]);
  });
});
