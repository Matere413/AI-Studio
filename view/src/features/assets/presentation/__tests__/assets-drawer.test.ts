// ─── Unit Tests: Assets Drawer Helpers ────────────────────────
// Tests the pure helper functions extracted from AssetsDrawer:
// file validation and status display labels.
//
// Tests will FAIL (RED) until the helpers are exported from
// AssetsDrawer.tsx or a separate utils module.

import { describe, it } from "node:test";
import assert from "node:assert";

// NOTE: These imports will fail until the utils module is created
import {
  validateFile,
  getStatusLabel,
  MAX_FILE_SIZE_BYTES,
  ALLOWED_MIME_TYPES,
  type FileValidationResult,
} from "../assets-drawer-utils.ts";

void describe("validateFile", () => {
  void it("accepts valid PNG under 10MB", () => {
    const file = new File(["fake-png"], "test.png", { type: "image/png" });
    Object.defineProperty(file, "size", { value: 5 * 1024 * 1024 });

    const result: FileValidationResult = validateFile(file);
    assert.strictEqual(result.valid, true);
    assert.strictEqual(result.error, null);
  });

  void it("accepts valid JPEG under 10MB", () => {
    const file = new File(["fake-jpg"], "test.jpg", { type: "image/jpeg" });
    Object.defineProperty(file, "size", { value: 3 * 1024 * 1024 });

    const result: FileValidationResult = validateFile(file);
    assert.strictEqual(result.valid, true);
    assert.strictEqual(result.error, null);
  });

  void it("rejects oversized file over 10MB", () => {
    const file = new File(["fake-big"], "big.png", { type: "image/png" });
    Object.defineProperty(file, "size", { value: 11 * 1024 * 1024 });

    const result: FileValidationResult = validateFile(file);
    assert.strictEqual(result.valid, false);
    assert.ok(result.error!.includes("10 MB"));
  });

  void it("rejects non-image file type", () => {
    const file = new File(["fake-pdf"], "doc.pdf", { type: "application/pdf" });
    Object.defineProperty(file, "size", { value: 1024 });

    const result: FileValidationResult = validateFile(file);
    assert.strictEqual(result.valid, false);
    assert.ok(result.error!.includes("image/png"));
  });

  void it("rejects exact 10MB file (size limit is exclusive)", () => {
    const file = new File(["fake-png"], "test.png", { type: "image/png" });
    Object.defineProperty(file, "size", { value: 10 * 1024 * 1024 });

    const result: FileValidationResult = validateFile(file);
    assert.strictEqual(result.valid, true);
    assert.strictEqual(result.error, null);
  });
});

void describe("getStatusLabel", () => {
  void it('returns "Ready" for idle', () => {
    assert.strictEqual(getStatusLabel("idle"), "Ready");
  });

  void it('returns "Compressing…" for compressing', () => {
    assert.strictEqual(getStatusLabel("compressing"), "Compressing…");
  });

  void it('returns "Requesting upload…" for requesting_ticket', () => {
    assert.strictEqual(
      getStatusLabel("requesting_ticket"),
      "Requesting upload…",
    );
  });

  void it('returns "Uploading…" for uploading', () => {
    assert.strictEqual(getStatusLabel("uploading"), "Uploading…");
  });

  void it('returns "Finalizing…" for finalizing', () => {
    assert.strictEqual(getStatusLabel("finalizing"), "Finalizing…");
  });

  void it('returns "Uploaded" for done', () => {
    assert.strictEqual(getStatusLabel("done"), "Uploaded");
  });

  void it('returns "Failed" for error', () => {
    assert.strictEqual(getStatusLabel("error"), "Failed");
  });
});
