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

  // Raw HTML in a 422 top-level detail MUST NOT leak — a proxy/framework
  // debug page masquerading as a validation detail falls back to the
  // generic "Validation failed" message.
  void it("422 with raw HTML detail (doctype) → validation_error fallback, no HTML surfaced", () => {
    const result = normalizeError(422, {
      detail: "<!DOCTYPE html><html><body>422 Unprocessable Entity</body></html>",
    });
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  void it("422 with raw HTML detail (<html>) → validation_error fallback", () => {
    const result = normalizeError(422, {
      detail: "<html><head><title>422</title></head></html>",
    });
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  void it("422 with empty string detail → validation_error fallback", () => {
    const result = normalizeError(422, { detail: "" });
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

  // Raw HTML inside a 4xx `{ error: { detail } }` envelope MUST NOT leak
  // — the code is preserved, but the unsafe detail falls back to the
  // generic "Request failed" message.
  void it("400 with raw HTML in envelope detail (doctype) → code preserved, generic detail, no HTML surfaced", () => {
    const result = normalizeError(400, {
      error: {
        code: "bad_request",
        detail: "<!DOCTYPE html><html><body>400 Bad Request</body></html>",
      },
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("403 with raw HTML in envelope detail (<html>) → code preserved, generic detail", () => {
    const result = normalizeError(403, {
      error: {
        code: "forbidden",
        detail: "<html><head><title>403</title></head></html>",
      },
    });
    assert.strictEqual(result.code, "forbidden");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("429 with raw HTML in envelope detail (<body>) → code preserved, generic detail", () => {
    const result = normalizeError(429, {
      error: {
        code: "rate_limited",
        detail: "<body><h1>429 Too Many Requests</h1></body>",
      },
    });
    assert.strictEqual(result.code, "rate_limited");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx envelope with non-string detail (object) → code preserved, generic detail", () => {
    const result = normalizeError(400, {
      error: { code: "bad_request", detail: { nested: "object" } },
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx envelope with empty string detail → code preserved, generic detail", () => {
    const result = normalizeError(400, {
      error: { code: "bad_request", detail: "" },
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "Request failed");
  });

  // ── Plain `{ detail }` preservation (no error envelope) ────
  //
  // FastAPI/Starlette can emit a bare `{ detail: "..." }` body for non-422
  // errors (e.g. 400/401/403/409/429/5xx) without the `{ error: { code,
  // detail } }` wrapper. The normalizer MUST preserve a safe string detail
  // so Studio (which reads plain-object `.detail`) can surface the backend
  // message. The code stays the stable `unknown_error` so existing `code`
  // handling is retained.

  void it('400 with plain detail → preserves detail, code unknown_error', () => {
    const result = normalizeError(400, { detail: "Missing prompt field" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Missing prompt field");
  });

  void it('401 with plain detail → preserves detail', () => {
    const result = normalizeError(401, { detail: "Not authenticated" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Not authenticated");
  });

  void it('403 with plain detail → preserves detail', () => {
    const result = normalizeError(403, { detail: "Email verification is required" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Email verification is required");
  });

  void it('409 with plain detail → preserves detail', () => {
    const result = normalizeError(409, { detail: "An account with this email already exists" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "An account with this email already exists");
  });

  void it('429 with plain detail → preserves detail', () => {
    const result = normalizeError(429, { detail: "Too many requests" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Too many requests");
  });

  void it('500 with plain detail → preserves detail, code unknown_error', () => {
    const result = normalizeError(500, { detail: "Internal Server Error" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Internal Server Error");
  });

  void it('503 with plain detail → preserves detail', () => {
    const result = normalizeError(503, { detail: "Service unavailable" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Service unavailable");
  });

  // Non-string detail (HTML error page, object, number) MUST NOT be exposed.
  void it("500 with raw HTML detail (doctype) → generic fallback, no HTML surfaced", () => {
    const result = normalizeError(500, {
      detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>",
    });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("502 with raw HTML detail (<html>) → generic fallback", () => {
    const result = normalizeError(502, {
      detail: "<html><head><title>502</title></head></html>",
    });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  // Ordinary text with angle-bracket comparisons (NOT markup) is preserved.
  // The guard rejects only strings that contain actual HTML tags or
  // declarations; a `<` used as a comparison operator (followed by a space
  // or a non-tag character) is safe and kept as-is.
  void it("400 with comparison text (a < b) → preserved as string, not treated as markup", () => {
    const result = normalizeError(400, { detail: "Value must be < 100 and > 0" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Value must be < 100 and > 0");
  });

  void it("400 with dangling angle bracket (no tag) → preserved as string", () => {
    const result = normalizeError(400, { detail: "Use < not empty" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Use < not empty");
  });

  // ── HTML fragments (tags) MUST fall back via the shared helper ────
  //
  // The guard rejects any string containing actual HTML markup, not only
  // document-shaped pages. `<script>`, `<div>`, and closing tags are
  // rejected through EVERY detail source (422 top-level, 4xx envelope,
  // 4xx plain, 5xx envelope, 5xx plain) so unsafe fragments never leak.

  void it("422 with <script> fragment detail → validation_error fallback, no HTML surfaced", () => {
    const result = normalizeError(422, { detail: "<script>alert(1)</script>" });
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  void it("422 with <div> fragment detail → validation_error fallback", () => {
    const result = normalizeError(422, { detail: "<div>422 Unprocessable</div>" });
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Validation failed");
  });

  void it("4xx envelope with <script> fragment detail → code preserved, generic detail, no HTML surfaced", () => {
    const result = normalizeError(400, {
      error: { code: "bad_request", detail: "<script>alert(1)</script>" },
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx envelope with <div> fragment detail → code preserved, generic detail", () => {
    const result = normalizeError(403, {
      error: { code: "forbidden", detail: "<div>Forbidden</div>" },
    });
    assert.strictEqual(result.code, "forbidden");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx envelope with closing tag fragment detail → code preserved, generic detail", () => {
    const result = normalizeError(409, {
      error: { code: "conflict", detail: "oops </div> tail" },
    });
    assert.strictEqual(result.code, "conflict");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx plain detail with <script> fragment → generic fallback, no HTML surfaced", () => {
    const result = normalizeError(400, { detail: "<script>alert(1)</script>" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("4xx plain detail with <div> fragment → generic fallback", () => {
    const result = normalizeError(400, { detail: "<div>bad request</div>" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx envelope with <script> fragment detail → code preserved, generic detail, no HTML surfaced", () => {
    const result = normalizeError(500, {
      error: { code: "model_busy", detail: "<script>alert(1)</script>" },
    });
    assert.strictEqual(result.code, "model_busy");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx envelope with <div> fragment detail → code preserved, generic detail", () => {
    const result = normalizeError(502, {
      error: { code: "bad_gateway", detail: "<div>502</div>" },
    });
    assert.strictEqual(result.code, "bad_gateway");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx plain detail with <script> fragment → generic fallback, no HTML surfaced", () => {
    const result = normalizeError(500, { detail: "<script>alert(1)</script>" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx plain detail with <div> fragment → generic fallback", () => {
    const result = normalizeError(502, { detail: "<div>Bad Gateway</div>" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  // Document-shaped HTML is still rejected (covered by the same markup
  // guard) — kept as an explicit belt-and-suspenders assertion.
  void it("400 with <html> document fragment → generic fallback", () => {
    const result = normalizeError(400, { detail: "<html>oops</html>" });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("400 with object detail → generic fallback (no unsafe structure)", () => {
    const result = normalizeError(400, { detail: { nested: "object" } });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("500 with number detail → generic fallback", () => {
    const result = normalizeError(500, { detail: 12345 });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("500 with array detail → generic fallback", () => {
    const result = normalizeError(500, { detail: ["err1", "err2"] });
    assert.strictEqual(result.code, "unknown_error");
    assert.strictEqual(result.detail, "Request failed");
  });

  // Envelope takes priority over plain detail.
  void it("400 with envelope AND plain detail → envelope wins", () => {
    const result = normalizeError(400, {
      error: { code: "bad_request", detail: "From envelope" },
      detail: "From plain field",
    });
    assert.strictEqual(result.code, "bad_request");
    assert.strictEqual(result.detail, "From envelope");
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

  // Raw HTML inside a 5xx `{ error: { detail } }` envelope MUST NOT leak
  // — the code is preserved, but the unsafe detail falls back to the
  // generic "Request failed" message.
  void it("500 with raw HTML in envelope detail (doctype) → code preserved, generic detail, no HTML surfaced", () => {
    const result = normalizeError(500, {
      error: {
        code: "model_busy",
        detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>",
      },
    });
    assert.strictEqual(result.code, "model_busy");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("502 with raw HTML in envelope detail (<html>) → code preserved, generic detail", () => {
    const result = normalizeError(502, {
      error: {
        code: "bad_gateway",
        detail: "<html><head><title>502</title></head></html>",
      },
    });
    assert.strictEqual(result.code, "bad_gateway");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("503 with raw HTML in envelope detail (<body>) → code preserved, generic detail", () => {
    const result = normalizeError(503, {
      error: {
        code: "service_unavailable",
        detail: "<body><h1>503 Service Unavailable</h1></body>",
      },
    });
    assert.strictEqual(result.code, "service_unavailable");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx envelope with non-string detail (number) → code preserved, generic detail", () => {
    const result = normalizeError(500, {
      error: { code: "model_busy", detail: 12345 },
    });
    assert.strictEqual(result.code, "model_busy");
    assert.strictEqual(result.detail, "Request failed");
  });

  void it("5xx envelope with empty string detail → code preserved, generic detail", () => {
    const result = normalizeError(500, {
      error: { code: "model_busy", detail: "" },
    });
    assert.strictEqual(result.code, "model_busy");
    assert.strictEqual(result.detail, "Request failed");
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
