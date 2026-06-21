// ─── Integration Tests: Image Proxy Route ─────────────────────
// Tests the `/api/images/[jobId]` Next.js route handler that
// proxies to the backend image service.
//
// Covers:
// - 200: streams binary with upstream Content-Type
// - 404: returns error JSON { code, detail }
// - 500+ / errors: returns error JSON

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { GET } from "../images/[jobId]/route.ts";

// ─── Setup / Teardown ─────────────────────────────────────────

const ORIGINAL_FETCH = globalThis.fetch;

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = ORIGINAL_FETCH;
});

// ─── Helpers ──────────────────────────────────────────────────

function mockImageResponse(
  status: number,
  body: BodyInit | null,
  headers?: Record<string, string>,
): void {
  globalThis.fetch = async () =>
    new Response(body, {
      status,
      statusText: status >= 400 ? "Error" : "OK",
      headers: {
        "content-type": headers?.["content-type"] ?? "image/png",
        ...headers,
      },
    });
}

function mockNetworkError(): void {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
}

// ─── Tests ────────────────────────────────────────────────────

void describe("GET /api/images/[jobId]", () => {
  void it("proxies to the correct backend URL", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response("image-data", { status: 200 });
    };

    const req = new Request("http://localhost:3000/api/images/test-123");
    await GET(req, { params: { jobId: "test-123" } });

    assert.strictEqual(
      calledUrl,
      "http://backend.example.com/images/test-123",
    );
  });

  void it("returns 200 with binary body and correct Content-Type", async () => {
    const imageData = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
    mockImageResponse(200, imageData, { "content-type": "image/png" });

    const req = new Request("http://localhost:3000/api/images/img-ok");
    const response = await GET(req, { params: { jobId: "img-ok" } });

    assert.strictEqual(response.status, 200);
    assert.strictEqual(
      response.headers.get("content-type"),
      "image/png",
    );

    const body = await response.arrayBuffer();
    assert.deepStrictEqual(new Uint8Array(body), imageData);
  });

  void it("returns 404 with error JSON when backend returns 404", async () => {
    mockImageResponse(404, JSON.stringify({
      code: "not_found",
      detail: "Image not found",
    }), { "content-type": "application/json" });

    const req = new Request("http://localhost:3000/api/images/missing");
    const response = await GET(req, { params: { jobId: "missing" } });

    assert.strictEqual(response.status, 404);
    assert.strictEqual(
      response.headers.get("content-type"),
      "application/json",
    );

    const body = await response.json();
    assert.strictEqual(body.code, "not_found");
    assert.strictEqual(body.detail, "Image not found");
  });

  void it("returns 404 with error JSON when backend 404 has no body", async () => {
    mockImageResponse(404, null, { "content-type": "application/json" });

    const req = new Request("http://localhost:3000/api/images/no-body");
    const response = await GET(req, { params: { jobId: "no-body" } });

    assert.strictEqual(response.status, 404);
    const body = await response.json();
    assert.strictEqual(body.code, "not_found");
    assert.strictEqual(body.detail, "Image not found");
  });

  void it("returns 502 on network error", async () => {
    mockNetworkError();

    const req = new Request("http://localhost:3000/api/images/network-fail");
    const response = await GET(req, { params: { jobId: "network-fail" } });

    assert.strictEqual(response.status, 502);
    const body = await response.json();
    assert.strictEqual(body.code, "bad_gateway");
    assert.strictEqual(body.detail, "Upstream connection failed");
  });

  void it("returns 502 on backend 500+ errors", async () => {
    mockImageResponse(500, JSON.stringify({
      code: "server_error",
      detail: "Internal error",
    }), { "content-type": "application/json" });

    const req = new Request("http://localhost:3000/api/images/server-error");
    const response = await GET(req, { params: { jobId: "server-error" } });

    assert.strictEqual(response.status, 502);
    const body = await response.json();
    assert.strictEqual(body.code, "bad_gateway");
    assert.strictEqual(body.detail, "Backend returned 500");
  });
});
