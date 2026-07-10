// ─── Unit Tests: normalizeError ──────────────────────────────
// Tests the backend error envelope normalization.

import { describe, it } from "node:test";
import assert from "node:assert";
import { normalizeError } from "../api-client.ts";

interface NormalizeErrorCase {
  name: string;
  status: number;
  body: unknown;
  expected: { code: string; detail: string };
}

function assertNormalized({ name, status, body, expected }: NormalizeErrorCase): void {
  const result = normalizeError(status, body);
  assert.strictEqual(result.code, expected.code, `${name}: preserves the expected error code`);
  assert.strictEqual(
    result.detail,
    expected.detail,
    `${name}: preserves the expected error detail`,
  );
}

function addCases(cases: NormalizeErrorCase[]): void {
  for (const testCase of cases) {
    void it(testCase.name, () => assertNormalized(testCase));
  }
}

const REQUEST_FAILED = { code: "unknown_error", detail: "Request failed" };
const VALIDATION_FAILED = { code: "validation_error", detail: "Validation failed" };

void describe("normalizeError", () => {
  // 422 validation details use their own fallback and reject unsafe markup.
  addCases([
    {
      name: '422 with string detail → "validation_error"',
      status: 422,
      body: { detail: "Invalid prompt" },
      expected: { code: "validation_error", detail: "Invalid prompt" },
    },
    {
      name: "422 with missing detail → fallback message",
      status: 422,
      body: {},
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with null body → fallback message",
      status: 422,
      body: null,
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with raw HTML detail (doctype) → validation_error fallback, no HTML surfaced",
      status: 422,
      body: { detail: "<!DOCTYPE html><html><body>422 Unprocessable Entity</body></html>" },
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with raw HTML detail (<html>) → validation_error fallback",
      status: 422,
      body: { detail: "<html><head><title>422</title></head></html>" },
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with empty string detail → validation_error fallback",
      status: 422,
      body: { detail: "" },
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with <script> fragment detail → validation_error fallback, no HTML surfaced",
      status: 422,
      body: { detail: "<script>alert(1)</script>" },
      expected: VALIDATION_FAILED,
    },
    {
      name: "422 with <div> fragment detail → validation_error fallback",
      status: 422,
      body: { detail: "<div>422 Unprocessable</div>" },
      expected: VALIDATION_FAILED,
    },
  ]);

  // 4xx and 5xx envelopes preserve their codes, but safeDetailOr rejects
  // document HTML, tag fragments, non-string values, and empty strings.
  addCases([
    {
      name: "400 with error envelope → passthrough code and detail",
      status: 400,
      body: { error: { code: "bad_request", detail: "Missing prompt field" } },
      expected: { code: "bad_request", detail: "Missing prompt field" },
    },
    {
      name: "403 with envelope → uses embedded code",
      status: 403,
      body: { error: { code: "forbidden", detail: "Insufficient credits" } },
      expected: { code: "forbidden", detail: "Insufficient credits" },
    },
    {
      name: "500 with error envelope → passthrough code and detail",
      status: 500,
      body: { error: { code: "model_busy", detail: "All GPUs are occupied" } },
      expected: { code: "model_busy", detail: "All GPUs are occupied" },
    },
    {
      name: "502 with envelope → uses embedded code",
      status: 502,
      body: { error: { code: "bad_gateway", detail: "Upstream timeout" } },
      expected: { code: "bad_gateway", detail: "Upstream timeout" },
    },
    {
      name: "400 with raw HTML in envelope detail (doctype) → code preserved, generic detail, no HTML surfaced",
      status: 400,
      body: {
        error: {
          code: "bad_request",
          detail: "<!DOCTYPE html><html><body>400 Bad Request</body></html>",
        },
      },
      expected: { code: "bad_request", detail: "Request failed" },
    },
    {
      name: "403 with raw HTML in envelope detail (<html>) → code preserved, generic detail",
      status: 403,
      body: {
        error: { code: "forbidden", detail: "<html><head><title>403</title></head></html>" },
      },
      expected: { code: "forbidden", detail: "Request failed" },
    },
    {
      name: "429 with raw HTML in envelope detail (<body>) → code preserved, generic detail",
      status: 429,
      body: {
        error: { code: "rate_limited", detail: "<body><h1>429 Too Many Requests</h1></body>" },
      },
      expected: { code: "rate_limited", detail: "Request failed" },
    },
    {
      name: "500 with raw HTML in envelope detail (doctype) → code preserved, generic detail, no HTML surfaced",
      status: 500,
      body: {
        error: {
          code: "model_busy",
          detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>",
        },
      },
      expected: { code: "model_busy", detail: "Request failed" },
    },
    {
      name: "502 with raw HTML in envelope detail (<html>) → code preserved, generic detail",
      status: 502,
      body: {
        error: { code: "bad_gateway", detail: "<html><head><title>502</title></head></html>" },
      },
      expected: { code: "bad_gateway", detail: "Request failed" },
    },
    {
      name: "503 with raw HTML in envelope detail (<body>) → code preserved, generic detail",
      status: 503,
      body: {
        error: {
          code: "service_unavailable",
          detail: "<body><h1>503 Service Unavailable</h1></body>",
        },
      },
      expected: { code: "service_unavailable", detail: "Request failed" },
    },
    {
      name: "4xx envelope with non-string detail (object) → code preserved, generic detail",
      status: 400,
      body: { error: { code: "bad_request", detail: { nested: "object" } } },
      expected: { code: "bad_request", detail: "Request failed" },
    },
    {
      name: "5xx envelope with non-string detail (number) → code preserved, generic detail",
      status: 500,
      body: { error: { code: "model_busy", detail: 12345 } },
      expected: { code: "model_busy", detail: "Request failed" },
    },
    {
      name: "4xx envelope with empty string detail → code preserved, generic detail",
      status: 400,
      body: { error: { code: "bad_request", detail: "" } },
      expected: { code: "bad_request", detail: "Request failed" },
    },
    {
      name: "5xx envelope with empty string detail → code preserved, generic detail",
      status: 500,
      body: { error: { code: "model_busy", detail: "" } },
      expected: { code: "model_busy", detail: "Request failed" },
    },
    {
      name: "4xx envelope with <script> fragment detail → code preserved, generic detail, no HTML surfaced",
      status: 400,
      body: { error: { code: "bad_request", detail: "<script>alert(1)</script>" } },
      expected: { code: "bad_request", detail: "Request failed" },
    },
    {
      name: "4xx envelope with <div> fragment detail → code preserved, generic detail",
      status: 403,
      body: { error: { code: "forbidden", detail: "<div>Forbidden</div>" } },
      expected: { code: "forbidden", detail: "Request failed" },
    },
    {
      name: "4xx envelope with closing tag fragment detail → code preserved, generic detail",
      status: 409,
      body: { error: { code: "conflict", detail: "oops </div> tail" } },
      expected: { code: "conflict", detail: "Request failed" },
    },
    {
      name: "5xx envelope with <script> fragment detail → code preserved, generic detail, no HTML surfaced",
      status: 500,
      body: { error: { code: "model_busy", detail: "<script>alert(1)</script>" } },
      expected: { code: "model_busy", detail: "Request failed" },
    },
    {
      name: "5xx envelope with <div> fragment detail → code preserved, generic detail",
      status: 502,
      body: { error: { code: "bad_gateway", detail: "<div>502</div>" } },
      expected: { code: "bad_gateway", detail: "Request failed" },
    },
  ]);

  // Plain FastAPI/Starlette details retain safe text with the stable code.
  addCases([
    {
      name: "400 with plain detail → preserves detail, code unknown_error",
      status: 400,
      body: { detail: "Missing prompt field" },
      expected: { code: "unknown_error", detail: "Missing prompt field" },
    },
    {
      name: "401 with plain detail → preserves detail",
      status: 401,
      body: { detail: "Not authenticated" },
      expected: { code: "unknown_error", detail: "Not authenticated" },
    },
    {
      name: "403 with plain detail → preserves detail",
      status: 403,
      body: { detail: "Email verification is required" },
      expected: { code: "unknown_error", detail: "Email verification is required" },
    },
    {
      name: "409 with plain detail → preserves detail",
      status: 409,
      body: { detail: "An account with this email already exists" },
      expected: { code: "unknown_error", detail: "An account with this email already exists" },
    },
    {
      name: "429 with plain detail → preserves detail",
      status: 429,
      body: { detail: "Too many requests" },
      expected: { code: "unknown_error", detail: "Too many requests" },
    },
    {
      name: "500 with plain detail → preserves detail, code unknown_error",
      status: 500,
      body: { detail: "Internal Server Error" },
      expected: { code: "unknown_error", detail: "Internal Server Error" },
    },
    {
      name: "503 with plain detail → preserves detail",
      status: 503,
      body: { detail: "Service unavailable" },
      expected: { code: "unknown_error", detail: "Service unavailable" },
    },
    {
      name: "400 with comparison text (a < b) → preserved as string, not treated as markup",
      status: 400,
      body: { detail: "Value must be < 100 and > 0" },
      expected: { code: "unknown_error", detail: "Value must be < 100 and > 0" },
    },
    {
      name: "400 with dangling angle bracket (no tag) → preserved as string",
      status: 400,
      body: { detail: "Use < not empty" },
      expected: { code: "unknown_error", detail: "Use < not empty" },
    },
    {
      name: "500 with raw HTML detail (doctype) → generic fallback, no HTML surfaced",
      status: 500,
      body: { detail: "<!DOCTYPE html><html><body>502 Bad Gateway</body></html>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "502 with raw HTML detail (<html>) → generic fallback",
      status: 502,
      body: { detail: "<html><head><title>502</title></head></html>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "4xx plain detail with <script> fragment → generic fallback, no HTML surfaced",
      status: 400,
      body: { detail: "<script>alert(1)</script>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "4xx plain detail with <div> fragment → generic fallback",
      status: 400,
      body: { detail: "<div>bad request</div>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "5xx plain detail with <script> fragment → generic fallback, no HTML surfaced",
      status: 500,
      body: { detail: "<script>alert(1)</script>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "5xx plain detail with <div> fragment → generic fallback",
      status: 502,
      body: { detail: "<div>Bad Gateway</div>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "400 with <html> document fragment → generic fallback",
      status: 400,
      body: { detail: "<html>oops</html>" },
      expected: REQUEST_FAILED,
    },
    {
      name: "400 with object detail → generic fallback (no unsafe structure)",
      status: 400,
      body: { detail: { nested: "object" } },
      expected: REQUEST_FAILED,
    },
    {
      name: "500 with number detail → generic fallback",
      status: 500,
      body: { detail: 12345 },
      expected: REQUEST_FAILED,
    },
    {
      name: "500 with array detail → generic fallback",
      status: 500,
      body: { detail: ["err1", "err2"] },
      expected: REQUEST_FAILED,
    },
  ]);

  addCases([
    {
      name: "400 with missing error field → unknown_error fallback",
      status: 400,
      body: {},
      expected: REQUEST_FAILED,
    },
    {
      name: "400 with null body → unknown_error fallback",
      status: 400,
      body: null,
      expected: REQUEST_FAILED,
    },
    {
      name: "500 with missing error field → unknown_error fallback",
      status: 500,
      body: {},
      expected: REQUEST_FAILED,
    },
    {
      name: "400 with envelope AND plain detail → envelope wins",
      status: 400,
      body: { error: { code: "bad_request", detail: "From envelope" }, detail: "From plain field" },
      expected: { code: "bad_request", detail: "From envelope" },
    },
    {
      name: "200 (non-error) → unknown_error fallback",
      status: 200,
      body: { ok: true },
      expected: REQUEST_FAILED,
    },
    {
      name: "undefined body at 418 → unknown_error fallback",
      status: 418,
      body: undefined,
      expected: REQUEST_FAILED,
    },
    {
      name: "non-object body (string) at 500 → unknown_error fallback",
      status: 500,
      body: "server error string",
      expected: REQUEST_FAILED,
    },
  ]);
});
