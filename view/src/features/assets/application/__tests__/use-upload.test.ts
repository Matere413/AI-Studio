// ─── Unit Tests: Upload Hook ───────────────────────────────────
// Tests the pure functions extracted from the upload state machine:
// compression parameters and status helper.
//
// These tests will FAIL (RED) until use-upload.ts is created.

import { describe, it } from "node:test";
import assert from "node:assert";

// NOTE: These imports will fail until use-upload.ts is created
import {
  getCompressionParams,
  isTerminalStatus,
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
