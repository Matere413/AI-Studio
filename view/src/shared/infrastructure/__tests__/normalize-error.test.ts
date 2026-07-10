// ─── Unit Tests: normalizeError ──────────────────────────────
// Tests the backend error envelope normalization.

import { describe, it } from "node:test";
import assert from "node:assert";
import { normalizeError } from "../api-client.ts";

type Expected = { code: string; detail: string };
type Case = readonly [name: string, status: number, body: unknown, expected: Expected];

const FAILED = { code: "unknown_error", detail: "Request failed" };
const INVALID = { code: "validation_error", detail: "Validation failed" };

// prettier-ignore
const cases: Case[] = [
  ['422 safe detail', 422, { detail: "Invalid prompt" }, { code: "validation_error", detail: "Invalid prompt" }],
  ["422 missing detail", 422, {}, INVALID], ["422 null body", 422, null, INVALID],
  ["422 doctype", 422, { detail: "<!DOCTYPE html><html><body>422 Unprocessable Entity</body></html>" }, INVALID],
  ["422 html", 422, { detail: "<html><head><title>422</title></head></html>" }, INVALID], ["422 empty detail", 422, { detail: "" }, INVALID],
  ["422 script fragment", 422, { detail: "<script>alert(1)</script>" }, INVALID], ["422 div fragment", 422, { detail: "<div>422 Unprocessable</div>" }, INVALID],
  ["4xx safe envelope", 400, { error: { code: "bad_request", detail: "Missing prompt field" } }, { code: "bad_request", detail: "Missing prompt field" }],
  ["4xx embedded code", 403, { error: { code: "forbidden", detail: "Insufficient credits" } }, { code: "forbidden", detail: "Insufficient credits" }],
  ["5xx safe envelope", 500, { error: { code: "model_busy", detail: "All GPUs are occupied" } }, { code: "model_busy", detail: "All GPUs are occupied" }],
  ["5xx embedded code", 502, { error: { code: "bad_gateway", detail: "Upstream timeout" } }, { code: "bad_gateway", detail: "Upstream timeout" }],
  ["4xx envelope doctype", 400, { error: { code: "bad_request", detail: "<!DOCTYPE html><html><body>400 Bad Request</body></html>" } }, { code: "bad_request", detail: "Request failed" }],
  ["4xx envelope html", 403, { error: { code: "forbidden", detail: "<html><head><title>403</title></head></html>" } }, { code: "forbidden", detail: "Request failed" }],
  ["4xx envelope body", 429, { error: { code: "rate_limited", detail: "<body><h1>429 Too Many Requests</h1></body>" } }, { code: "rate_limited", detail: "Request failed" }],
  ["5xx envelope doctype", 500, { error: { code: "model_busy", detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>" } }, { code: "model_busy", detail: "Request failed" }],
  ["5xx envelope html", 502, { error: { code: "bad_gateway", detail: "<html><head><title>502</title></head></html>" } }, { code: "bad_gateway", detail: "Request failed" }],
  ["5xx envelope body", 503, { error: { code: "service_unavailable", detail: "<body><h1>503 Service Unavailable</h1></body>" } }, { code: "service_unavailable", detail: "Request failed" }],
  ["4xx envelope object", 400, { error: { code: "bad_request", detail: { nested: "object" } } }, { code: "bad_request", detail: "Request failed" }],
  ["5xx envelope number", 500, { error: { code: "model_busy", detail: 12345 } }, { code: "model_busy", detail: "Request failed" }],
  ["4xx envelope empty", 400, { error: { code: "bad_request", detail: "" } }, { code: "bad_request", detail: "Request failed" }],
  ["5xx envelope empty", 500, { error: { code: "model_busy", detail: "" } }, { code: "model_busy", detail: "Request failed" }],
  ["4xx envelope script", 400, { error: { code: "bad_request", detail: "<script>alert(1)</script>" } }, { code: "bad_request", detail: "Request failed" }],
  ["4xx envelope div", 403, { error: { code: "forbidden", detail: "<div>Forbidden</div>" } }, { code: "forbidden", detail: "Request failed" }],
  ["4xx envelope closing tag", 409, { error: { code: "conflict", detail: "oops </div> tail" } }, { code: "conflict", detail: "Request failed" }],
  ["5xx envelope script", 500, { error: { code: "model_busy", detail: "<script>alert(1)</script>" } }, { code: "model_busy", detail: "Request failed" }],
  ["5xx envelope div", 502, { error: { code: "bad_gateway", detail: "<div>502</div>" } }, { code: "bad_gateway", detail: "Request failed" }],
  ["400 plain safe", 400, { detail: "Missing prompt field" }, { code: "unknown_error", detail: "Missing prompt field" }],
  ["401 plain safe", 401, { detail: "Not authenticated" }, { code: "unknown_error", detail: "Not authenticated" }],
  ["403 plain safe", 403, { detail: "Email verification is required" }, { code: "unknown_error", detail: "Email verification is required" }],
  ["409 plain safe", 409, { detail: "An account with this email already exists" }, { code: "unknown_error", detail: "An account with this email already exists" }],
  ["429 plain safe", 429, { detail: "Too many requests" }, { code: "unknown_error", detail: "Too many requests" }],
  ["500 plain safe", 500, { detail: "Internal Server Error" }, { code: "unknown_error", detail: "Internal Server Error" }],
  ["503 plain safe", 503, { detail: "Service unavailable" }, { code: "unknown_error", detail: "Service unavailable" }],
  ["plain comparison text", 400, { detail: "Value must be < 100 and > 0" }, { code: "unknown_error", detail: "Value must be < 100 and > 0" }],
  ["plain dangling bracket", 400, { detail: "Use < not empty" }, { code: "unknown_error", detail: "Use < not empty" }],
  ["5xx plain doctype", 500, { detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>" }, FAILED],
  ["5xx plain html", 502, { detail: "<html><head><title>502</title></head></html>" }, FAILED], ["4xx plain script", 400, { detail: "<script>alert(1)</script>" }, FAILED],
  ["4xx plain div", 400, { detail: "<div>bad request</div>" }, FAILED], ["5xx plain script", 500, { detail: "<script>alert(1)</script>" }, FAILED],
  ["5xx plain div", 502, { detail: "<div>Bad Gateway</div>" }, FAILED], ["4xx plain html", 400, { detail: "<html>oops</html>" }, FAILED],
  ["4xx plain object", 400, { detail: { nested: "object" } }, FAILED], ["5xx plain number", 500, { detail: 12345 }, FAILED],
  ["5xx plain array", 500, { detail: ["err1", "err2"] }, FAILED], ["4xx missing error", 400, {}, FAILED], ["4xx null body", 400, null, FAILED],
  ["5xx missing error", 500, {}, FAILED],
  ["envelope priority", 400, { error: { code: "bad_request", detail: "From envelope" }, detail: "From plain field" }, { code: "bad_request", detail: "From envelope" }],
  ["non-error status", 200, { ok: true }, FAILED], ["undefined body", 418, undefined, FAILED], ["non-object body", 500, "server error string", FAILED],
];

void describe("normalizeError", () => {
  for (const [name, status, body, expected] of cases) {
    void it(name, () => {
      const result = normalizeError(status, body);
      assert.strictEqual(result.code, expected.code, `${name}: expected error code`);
      assert.strictEqual(result.detail, expected.detail, `${name}: expected error detail`);
    });
  }
});
