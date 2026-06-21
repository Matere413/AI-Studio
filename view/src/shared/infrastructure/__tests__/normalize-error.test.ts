// ─── Unit Tests: normalizeError ──────────────────────────────
// Tests the backend error envelope normalization.

import { describe, it } from "node:test";
import assert from "node:assert";
import { normalizeError } from "../api-client.ts";

void describe("normalizeError", () => {
  // ── 422: Validation Error ─────────────────────────────────

  void it('422 with string detail → "validation_error"', () => {
    const result = normalizeError(422, { detail: "Invalid prompt" });
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Invalid prompt");
  });

  void it('422 with missing detail → fallback message', () => {
    const result = normalizeError(422, {});
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  void it("422 with null body → fallback message", () => {
    const result = normalizeError(422, null);
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  // ── 4xx: Client Error Envelope ────────────────────────────

  void it('400 with error envelope → passthrough code and detail', () => {
    const result = normalizeError(400, {
      error: { code: "bad_request", detail: "Missing prompt field" },
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "Missing prompt field");
  });

  void it("400 with missing error field → unknown_error fallback", () => {
    const result = normalizeError(400, {});
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("400 with null body → unknown_error fallback", () => {
    const result = normalizeError(400, null);
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("403 with envelope → uses embedded code", () => {
    const result = normalizeError(403, {
      error: { code: "forbidden", detail: "Insufficient credits" },
    });
    assert.strictEqual(result.code, "forbidden");
    assert.strictEqual(result.detail, "Insufficient credits");
  });

  // ── 5xx: Server Error Envelope ────────────────────────────

  void it('500 with error envelope → passthrough, default code "operational"', () => {
    const result = normalizeError(500, {
      error: { code: "model_busy", detail: "All GPUs are occupied" },
    });
    assert.strictEqual(result.code, "model_busy");
    assert.strictEqual(result.detail, "All GPUs are occupied");
  });

  void it("500 with missing error field → unknown_error fallback", () => {
    const result = normalizeError(500, {});
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("502 with envelope → operational", () => {
    const result = normalizeError(502, {
      error: { code: "bad_gateway", detail: "Upstream timeout" },
    });
    assert.strictEqual(result.code, "bad_gateway");
    assert.strictEqual(result.detail, "Upstream timeout");
  });

  // ── Unknown / Fallback ────────────────────────────────────

  void it("200 (non-error) → unknown_error fallback", () => {
    const result = normalizeError(200, { ok: true });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("undefined body at 418 → unknown_error fallback", () => {
    const result = normalizeError(418, undefined);
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("non-object body (string) at 500 → unknown_error fallback", () => {
    const result = normalizeError(500, "server error string");
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });
});
