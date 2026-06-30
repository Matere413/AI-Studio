// ─── Integration Tests: R2 Proxy Route ─────────────────────────
// Tests the `/api/r2/[...r2_key]` Next.js route handler that proxies
// browser-native image requests to the backend and preserves redirects.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { GET } from "../r2/[...r2_key]/route.ts";

const ORIGINAL_FETCH = globalThis.fetch;
const ORIGINAL_SET_TIMEOUT = globalThis.setTimeout;
const ORIGINAL_CLEAR_TIMEOUT = globalThis.clearTimeout;
const ORIGINAL_CONSOLE_ERROR = console.error;

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = ORIGINAL_FETCH;
  globalThis.setTimeout = ORIGINAL_SET_TIMEOUT;
  globalThis.clearTimeout = ORIGINAL_CLEAR_TIMEOUT;
  console.error = ORIGINAL_CONSOLE_ERROR;
});

void describe("GET /api/r2/[...r2_key]", () => {
  void it("forwards the cookie session and preserves a backend 307 redirect", async () => {
    let calledUrl = "";
    let calledRedirect = "";
    let calledSession = "";

    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      calledRedirect = (init as RequestInit).redirect ?? "";
      const headers = (init as RequestInit).headers as Record<string, string>;
      calledSession = headers["X-Session-ID"];
      return new Response(null, {
        status: 307,
        headers: {
          Location:
            "https://account-id.r2.cloudflarestorage.com/private-bucket/projects/p1/thumbnail.webp?X-Amz-Signature=test",
        },
      });
    };

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });

    assert.strictEqual(calledUrl, "http://backend.example.com/r2/projects/p1/thumbnail.webp");
    assert.strictEqual(calledRedirect, "manual");
    assert.strictEqual(calledSession, "session-cookie-123");
    assert.strictEqual(response.status, 307);
    assert.strictEqual(
      response.headers.get("location"),
      "https://account-id.r2.cloudflarestorage.com/private-bucket/projects/p1/thumbnail.webp?X-Amz-Signature=test",
    );
  });

  void it("rejects invalid r2_key values before backend fetch", async () => {
    let called = false;
    globalThis.fetch = async () => {
      called = true;
      return new Response(null, { status: 200 });
    };

    const req = new Request("http://localhost:3000/api/r2/../secret", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["..", "secret"] } });

    assert.strictEqual(response.status, 400);
    assert.strictEqual(called, false);
  });

  void it("rejects decoded embedded path separators, traversal, and malformed encoding before backend fetch", async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      return new Response(null, { status: 200 });
    };

    const invalidKeys: Array<string[] | string> = [
      ["%2F"],
      ["projects%2F..%2Fsecret"],
      ["..%2Fprojects"],
      ["projects%5C..%5Csecret"],
      ["..%5Cprojects"],
      ["projects", "%"],
    ];

    for (const r2Key of invalidKeys) {
      const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
        headers: { cookie: "ai-studio-session-id=session-cookie-123" },
      });

      const response = await GET(req, { params: { r2_key: r2Key } });
      const body = await response.json();

      assert.strictEqual(response.status, 400, `expected ${JSON.stringify(r2Key)} to be rejected`);
      assert.strictEqual(body.code, "invalid_r2_key");
    }

    assert.strictEqual(calls, 0);
  });

  void it("rejects double-encoded separators, traversal, and URL-control characters before backend fetch", async () => {
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      return new Response(null, { status: 200 });
    };

    const invalidKeys: Array<string[] | string> = [
      ["projects%252Fsecret"],
      ["projects%255Csecret"],
      ["%252e%252e"],
      ["thumbnail%3Fdownload=true"],
      ["thumbnail%23fragment"],
      ["thumbnail%253Fdownload=true"],
      ["thumbnail%2523fragment"],
    ];

    for (const r2Key of invalidKeys) {
      const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
        headers: { cookie: "ai-studio-session-id=session-cookie-123" },
      });

      const response = await GET(req, { params: { r2_key: r2Key } });
      const body = await response.json();

      assert.strictEqual(response.status, 400, `expected ${JSON.stringify(r2Key)} to be rejected`);
      assert.strictEqual(body.code, "invalid_r2_key");
    }

    assert.strictEqual(calls, 0);
  });

  void it("encodes validated path segments when calling the upstream backend", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response(null, {
        status: 307,
        headers: {
          Location:
            "https://account-id.r2.cloudflarestorage.com/private-bucket/projects/p1/image%20name.webp?X-Amz-Signature=test",
        },
      });
    };

    const req = new Request("http://localhost:3000/api/r2/projects/p1/image%20name.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "image%20name.webp"] } });

    assert.strictEqual(calledUrl, "http://backend.example.com/r2/projects/p1/image%20name.webp");
    assert.strictEqual(response.status, 307);
  });

  void it("returns 422 when the cookie session is missing", async () => {
    let called = false;
    globalThis.fetch = async () => {
      called = true;
      return new Response(null, { status: 200 });
    };

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp");
    const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });

    assert.strictEqual(response.status, 422);
    assert.strictEqual(called, false);
  });

  void it("returns 422 when the session cookie is malformed", async () => {
    let called = false;
    globalThis.fetch = async () => {
      called = true;
      return new Response(null, { status: 200 });
    };

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
      headers: { cookie: "ai-studio-session-id=%" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 422);
    assert.strictEqual(body.code, "missing_session");
    assert.strictEqual(called, false);
  });

  void it("returns 404 with a structured asset_not_found body for missing upstream assets", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ code: "asset_not_found", detail: "Asset not found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/missing.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "missing.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 404);
    assert.strictEqual(body.code, "asset_not_found");
    assert.strictEqual(body.detail, "Asset not found");
  });

  void it("returns a generic 503 when storage is unconfigured upstream", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ code: "internal_r2_unconfigured", detail: "bucket=private-assets" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/missing.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "missing.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 503);
    assert.strictEqual(body.code, "storage_not_configured");
    assert.strictEqual(body.detail, "Storage is not available");
    assert.notStrictEqual(body.code, "internal_r2_unconfigured");
    assert.notStrictEqual(body.detail, "bucket=private-assets");
  });

  void it("rejects unsafe upstream redirect locations with a generic 502 and logs server-side", async () => {
    const errors: unknown[][] = [];
    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.fetch = async () =>
      new Response(null, {
        status: 307,
        headers: { Location: "javascript:alert(document.cookie)" },
      });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 502);
    assert.strictEqual(body.code, "bad_gateway");
    assert.match(body.detail, /invalid redirect/i);
    assert.ok(errors.length > 0);
    assert.match(String(errors[0]?.[0] ?? ""), /unsafe|redirect/i);
  });

  void it("rejects upstream redirects outside the Cloudflare R2 storage origin allowlist", async () => {
    const errors: unknown[][] = [];
    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    const unsafeLocations = [
      "https://evil.example/projects/p1/thumbnail.webp?X-Amz-Signature=test",
      "http://account-id.r2.cloudflarestorage.com/private-bucket/projects/p1/thumbnail.webp",
      "/projects/p1/thumbnail.webp",
      "//evil.example/projects/p1/thumbnail.webp",
      "javascript:alert(document.cookie)",
    ];

    for (const location of unsafeLocations) {
      globalThis.fetch = async () =>
        new Response(null, {
          status: 307,
          headers: { Location: location },
        });

      const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
        headers: { cookie: "ai-studio-session-id=session-cookie-123" },
      });

      const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });
      const body = await response.json();

      assert.strictEqual(response.status, 502, `expected ${location} to be rejected`);
      assert.strictEqual(body.code, "bad_gateway");
      assert.match(body.detail, /invalid redirect/i);
    }

    assert.ok(errors.length >= unsafeLocations.length);
  });

  void it("returns 502 with a generic body and logs upstream 5xx failures", async () => {
    const errors: unknown[][] = [];
    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: "raw-botocore-stack" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/missing.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "missing.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 502);
    assert.strictEqual(body.code, "storage_error");
    assert.strictEqual(body.detail, "Unable to generate asset redirect");
    assert.ok(errors.length > 0);
    assert.match(String(errors[0]?.[0] ?? ""), /Upstream 5xx|storage/i);
  });

  void it("does not leak structured upstream 5xx error details", async () => {
    const errors: unknown[][] = [];
    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.fetch = async () =>
      new Response(JSON.stringify({ code: "internal_storage_exception", detail: "raw-r2-secret" }), {
        status: 500,
        headers: { "content-type": "application/json" },
      });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/missing.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "missing.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 502);
    assert.strictEqual(body.code, "storage_error");
    assert.strictEqual(body.detail, "Unable to generate asset redirect");
    assert.notStrictEqual(body.code, "internal_storage_exception");
    assert.notStrictEqual(body.detail, "raw-r2-secret");
    assert.ok(errors.length > 0);
  });

  void it("returns 502, clears the timer, and logs when the backend redirect is missing Location", async () => {
    let cleared = false;
    const errors: unknown[][] = [];

    globalThis.clearTimeout = ((timeoutId: ReturnType<typeof setTimeout>) => {
      cleared = true;
      return ORIGINAL_CLEAR_TIMEOUT(timeoutId);
    }) as typeof clearTimeout;

    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.fetch = async () => new Response(null, { status: 307 });

    const req = new Request("http://localhost:3000/api/r2/projects/p1/missing.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "missing.webp"] } });
    const body = await response.json();

    assert.strictEqual(response.status, 502);
    assert.strictEqual(body.code, "bad_gateway");
    assert.match(body.detail, /missing Location/i);
    assert.strictEqual(cleared, true);
    assert.ok(errors.length > 0);
    assert.match(String(errors[0]?.[0] ?? ""), /missing Location|malformed/i);
  });

  void it("bounds stalled upstream error body reads with the proxy timeout", async () => {
    let timeoutCallback: (() => void) | undefined;
    let cleared = false;
    const errors: unknown[][] = [];

    globalThis.setTimeout = ((callback: () => void) => {
      timeoutCallback = callback;
      return 0 as unknown as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout;

    globalThis.clearTimeout = (() => {
      cleared = true;
    }) as typeof clearTimeout;

    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.fetch = async (_url, init) => ({
      status: 500,
      ok: false,
      headers: new Headers(),
      json: async () => {
        queueMicrotask(() => {
          if (!cleared) timeoutCallback?.();
        });
        await new Promise<void>((resolve, reject) => {
          const signal = (init as RequestInit).signal;
          if (signal?.aborted) {
            reject(new DOMException("The operation was aborted", "AbortError"));
            return;
          }
          signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted", "AbortError"));
          });
        });
      },
    }) as unknown as Response;

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const result = await Promise.race([
      GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } }),
      new Promise<"unbounded">((resolve) => ORIGINAL_SET_TIMEOUT(() => resolve("unbounded"), 25)),
    ]);

    assert.notStrictEqual(result, "unbounded");
    const response = result as Response;
    const body = await response.json();

    assert.strictEqual(response.status, 502);
    assert.strictEqual(body.code, "storage_error");
    assert.strictEqual(body.detail, "Unable to generate asset redirect");
    assert.strictEqual(cleared, true);
    assert.ok(errors.length > 0);
  });

  void it("maps a timeout to a generic gateway error", async () => {
    const errors: unknown[][] = [];
    console.error = (...args: unknown[]) => {
      errors.push(args);
    };

    globalThis.setTimeout = ((callback: () => void) => {
      callback();
      return 0 as unknown as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout;

    globalThis.fetch = async (_url, init) => {
      if ((init as RequestInit).signal?.aborted) {
        throw new DOMException("The operation was aborted", "AbortError");
      }
      return new Promise<Response>(() => {
        // unreachable once the timeout aborts
      });
    };

    const req = new Request("http://localhost:3000/api/r2/projects/p1/thumbnail.webp", {
      headers: { cookie: "ai-studio-session-id=session-cookie-123" },
    });

    const response = await GET(req, { params: { r2_key: ["projects", "p1", "thumbnail.webp"] } });

    assert.strictEqual(response.status, 502);
    const body = await response.json();
    assert.strictEqual(body.code, "timeout");
    assert.ok(errors.length > 0);
    const logged = errors.flatMap((args) => args.map((part) => String(part)));
    assert.ok(logged.some((part) => /timeout|Abort/i.test(part)));
  });
});
