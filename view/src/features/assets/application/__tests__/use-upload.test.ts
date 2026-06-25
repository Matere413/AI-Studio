// ─── Unit Tests: Upload Hook ───────────────────────────────────
// Tests the pure functions extracted from the upload state machine:
// compression parameters, status helper, and upload orchestration.
//
// These tests will FAIL (RED) until use-upload.ts is created.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";

// NOTE: These imports will fail until use-upload.ts is created
import {
  getCompressionParams,
  isTerminalStatus,
  executeUploadFromBlob,
  type CompressionParams,
} from "../use-upload.ts";

void describe("getCompressionParams", () => {
  void it("shrinks image wider than max dimension", () => {
    const result = getCompressionParams(2000, 1000, 1024);
    assert.strictEqual(result.width, 1024);
    assert.strictEqual(result.height, 512);
  });

  void it("shrinks image taller than max dimension", () => {
    const result = getCompressionParams(1000, 2000, 1024);
    assert.strictEqual(result.width, 512);
    assert.strictEqual(result.height, 1024);
  });

  void it("keeps image smaller than max dimension unchanged", () => {
    const result = getCompressionParams(800, 600, 1024);
    assert.strictEqual(result.width, 800);
    assert.strictEqual(result.height, 600);
  });

  void it("handles square image at max dimension", () => {
    const result = getCompressionParams(1024, 1024, 1024);
    assert.strictEqual(result.width, 1024);
    assert.strictEqual(result.height, 1024);
  });

  void it("handles square image exceeding max dimension", () => {
    const result = getCompressionParams(2048, 2048, 1024);
    assert.strictEqual(result.width, 1024);
    assert.strictEqual(result.height, 1024);
  });

  void it("handles extreme aspect ratio (wide)", () => {
    const result = getCompressionParams(5000, 100, 1024);
    assert.strictEqual(result.width, 1024);
    // height = 1024 * (100/5000) = 20.48 → 20
    assert.strictEqual(result.height, 20);
  });

  void it("handles extreme aspect ratio (tall)", () => {
    const result = getCompressionParams(100, 5000, 1024);
    assert.strictEqual(result.width, 20);
    assert.strictEqual(result.height, 1024);
  });

  void it("uses default max dimension of 1024 when not specified", () => {
    const result = getCompressionParams(2000, 1500, 1024);
    assert.strictEqual(result.width, 1024);
    assert.strictEqual(result.height, 768);
  });

  void it("uses quality 0.85 by default", () => {
    const result = getCompressionParams(800, 600, 1024);
    assert.strictEqual(result.quality, 0.85);
  });

  void it("accepts custom quality", () => {
    const result = getCompressionParams(800, 600, 1024, 0.9);
    assert.strictEqual(result.quality, 0.9);
  });
});

void describe("isTerminalStatus", () => {
  void it("returns true for done", () => {
    assert.strictEqual(isTerminalStatus("done"), true);
  });

  void it("returns true for error", () => {
    assert.strictEqual(isTerminalStatus("error"), true);
  });

  void it("returns false for idle", () => {
    assert.strictEqual(isTerminalStatus("idle"), false);
  });

  void it("returns false for compressing", () => {
    assert.strictEqual(isTerminalStatus("compressing"), false);
  });

  void it("returns false for requesting_ticket", () => {
    assert.strictEqual(isTerminalStatus("requesting_ticket"), false);
  });

  void it("returns false for uploading", () => {
    assert.strictEqual(isTerminalStatus("uploading"), false);
  });

  void it("returns false for finalizing", () => {
    assert.strictEqual(isTerminalStatus("finalizing"), false);
  });
});

// ─── executeUploadFromBlob ─────────────────────────────────────

void describe("executeUploadFromBlob", () => {
  before(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
  });

  after(() => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  void it("calls finalizeAsset with server asset_id from ticket response", async () => {
    let finalizeUrl = "";

    globalThis.fetch = async (url, init) => {
      const urlStr = url.toString();
      if (urlStr.includes("upload-ticket")) {
        return new Response(
          JSON.stringify({
            asset_id: "server-asset-999",
            presigned_url: "https://r2.test/upload/f.webp",
            r2_key: "projects/p1/f.webp",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (urlStr.includes("r2.test")) {
        return new Response(null, { status: 200 });
      }
      if (urlStr.includes("finalize")) {
        finalizeUrl = urlStr;
        return new Response(
          JSON.stringify({
            id: "server-asset-999",
            r2_key: "projects/p1/f.webp",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(null, { status: 404 });
    };

    const result = await executeUploadFromBlob(
      "client-uuid",
      "test.webp",
      new Blob(["fake-webp"], { type: "image/webp" }),
      "image/webp",
      "p1",
    );

    // Verify finalizeAsset was called with SERVER asset_id, not client UUID
    assert.ok(
      finalizeUrl.includes("/assets/server-asset-999/finalize"),
      `Expected finalize URL with server asset_id, got: ${finalizeUrl}`,
    );
    assert.strictEqual(result.serverAssetId, "server-asset-999");
  });

  void it("returns r2Url built from finalized r2_key", async () => {
    globalThis.fetch = async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes("upload-ticket")) {
        return new Response(
          JSON.stringify({
            asset_id: "a1",
            presigned_url: "https://r2.test/upload/f.webp",
            r2_key: "projects/p1/f.webp",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (urlStr.includes("r2.test")) {
        return new Response(null, { status: 200 });
      }
      if (urlStr.includes("finalize")) {
        return new Response(
          JSON.stringify({
            id: "a1",
            r2_key: "projects/p1/a1.webp",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(null, { status: 404 });
    };

    const result = await executeUploadFromBlob(
      "client-uuid",
      "test.webp",
      new Blob(["fake-webp"], { type: "image/webp" }),
      "image/webp",
      "p1",
    );

    assert.ok(
      result.r2Url.includes("projects/p1/a1.webp"),
      `Expected r2Url to contain storage key, got: ${result.r2Url}`,
    );
  });

  void it("throws when R2 PUT fails", async () => {
    globalThis.fetch = async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes("upload-ticket")) {
        return new Response(
          JSON.stringify({
            asset_id: "a1",
            presigned_url: "https://r2.test/upload/f.webp",
            r2_key: "projects/p1/f.webp",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      if (urlStr.includes("r2.test")) {
        // Simulate R2 PUT failure
        return new Response(null, { status: 500 });
      }
      if (urlStr.includes("finalize")) {
        return new Response(
          JSON.stringify({ id: "a1" }),
          { status: 200, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(null, { status: 404 });
    };

    await assert.rejects(
      () =>
        executeUploadFromBlob(
          "client-uuid",
          "test.webp",
          new Blob(["fake-webp"], { type: "image/webp" }),
          "image/webp",
          "p1",
        ),
      { message: /R2 upload failed/ },
    );
  });

  void it("throws when requestUploadTicket fails", async () => {
    globalThis.fetch = async (url) => {
      const urlStr = url.toString();
      if (urlStr.includes("upload-ticket")) {
        return new Response(
          JSON.stringify({
            error: { code: "not_found", detail: "Project not found" },
          }),
          { status: 404, headers: { "content-type": "application/json" } },
        );
      }
      return new Response(null, { status: 404 });
    };

    await assert.rejects(
      () =>
        executeUploadFromBlob(
          "client-uuid",
          "test.webp",
          new Blob(["fake-webp"], { type: "image/webp" }),
          "image/webp",
          "p1",
        ),
    );
  });
});
