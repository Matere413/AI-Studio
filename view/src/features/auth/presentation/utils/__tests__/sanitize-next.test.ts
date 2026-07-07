// ─── Unit Tests: sanitizeNext ───────────────────────────────────
// Verifies the open-redirect guard used by LoginForm and RegisterForm
// on success. Only same-origin `/`-prefixed paths are accepted; any
// `:` in the path (covers `javascript:`, `data:`) and protocol-relative
// (`//evil.com`) are rejected.

import { describe, it } from "node:test";
import assert from "node:assert";
import { sanitizeNext } from "../sanitize-next.ts";

void describe("sanitizeNext", () => {
  void it("returns null for null input", () => {
    assert.strictEqual(sanitizeNext(null), null);
  });

  void it("returns null for undefined input", () => {
    assert.strictEqual(sanitizeNext(undefined), null);
  });

  void it("returns null for an empty string", () => {
    assert.strictEqual(sanitizeNext(""), null);
  });

  void it("passes through a same-origin absolute path", () => {
    assert.strictEqual(sanitizeNext("/studio"), "/studio");
  });

  void it("passes through a same-origin path with a query string", () => {
    assert.strictEqual(sanitizeNext("/studio?foo=1"), "/studio?foo=1");
  });

  void it("passes through a same-origin path with a query + fragment", () => {
    assert.strictEqual(sanitizeNext("/studio?foo=1#bar"), "/studio?foo=1#bar");
  });

  void it("rejects a protocol-relative URL (open-redirect vector)", () => {
    assert.strictEqual(sanitizeNext("//evil.com"), null);
  });

  void it("rejects a javascript: URL", () => {
    assert.strictEqual(sanitizeNext("javascript:alert(1)"), null);
  });

  void it("rejects any path containing a colon (blocks scheme injection)", () => {
    assert.strictEqual(sanitizeNext("/p:x"), null);
  });

  void it("rejects a relative path that does not start with /", () => {
    assert.strictEqual(sanitizeNext("studio"), null);
  });

  void it("rejects a full https URL", () => {
    assert.strictEqual(sanitizeNext("https://evil.com/path"), null);
  });
});