// ─── Unit Tests: API Client ──────────────────────────────────
// Tests submitGenerate and fetchImageBinary with mocked fetch.
// Uses Node built-in test runner — no Jest dependency.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { submitGenerate, fetchImageBinary, getWsUrl } from "../api-client.ts";
import type { GenerateRequest } from "@/features/chat/domain/dto";

// ─── Helpers ──────────────────────────────────────────────────

function mockFetchOnce(
  status: number,
  body: unknown,
  ok?: boolean,
): void {
  globalThis.fetch = async () =>
    new Response(JSON.stringify(body), {
      status,
      statusText: status >= 400 ? "Error" : "OK",
      headers: { "content-type": "application/json" },
    });
}

function mockFetchNetworkError(message: string): void {
  globalThis.fetch = async () => {
    throw new TypeError(message);
  };
}

function mockFetchAbort(): void {
  globalThis.fetch = async () => {
    const err = new DOMException("The operation was aborted", "AbortError");
    throw err;
  };
}

function mockFetchSlow(
  delayMs: number,
  status: number,
  body: unknown,
): void {
  globalThis.fetch = async (_input, init?: RequestInit) => {
    await new Promise((r) => setTimeout(r, delayMs));
    // If the signal was already aborted, simulate abort
    if (init?.signal?.aborted) {
      const err = new DOMException("The operation was aborted", "AbortError");
      throw err;
    }
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  };
}

// ─── Setup / Teardown ─────────────────────────────────────────

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
});

// ─── submitGenerate ────────────────────────────────────────────

void describe("submitGenerate", () => {
  void it("POSTs to the correct URL", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response(JSON.stringify({ job_id: "j1", status: "pending" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    const req: GenerateRequest = {
      workflow_name: "flux2_txt2img",
      prompt: "test",
    };
    await submitGenerate(req);
    assert.strictEqual(calledUrl, "http://test-api.example.com/generate");
  });

  void it("sends the correct Content-Type header", async () => {
    let contentType = "";
    globalThis.fetch = async (url, init) => {
      contentType = (init as RequestInit).headers!["Content-Type" as keyof HeadersInit] as string;
      return new Response(JSON.stringify({ job_id: "j2", status: "pending" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    const req: GenerateRequest = {
      workflow_name: "flux2_txt2img",
      prompt: "hello",
    };
    await submitGenerate(req);
    assert.strictEqual(contentType, "application/json");
  });

  void it("sends the full DTO as JSON body", async () => {
    let sentBody = "";
    globalThis.fetch = async (url, init) => {
      sentBody = (init as RequestInit).body as string;
      return new Response(JSON.stringify({ job_id: "j3", status: "pending" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    const req: GenerateRequest = {
      workflow_name: "identidad_gguf",
      prompt: "portrait",
      image_url: "http://example.com/face.png",
      width: 1024,
      height: 768,
      seed: 42,
    };
    await submitGenerate(req);
    const parsed = JSON.parse(sentBody);
    assert.strictEqual(parsed.workflow_name, "identidad_gguf");
    assert.strictEqual(parsed.prompt, "portrait");
    assert.strictEqual(parsed.image_url, "http://example.com/face.png");
    assert.strictEqual(parsed.width, 1024);
    assert.strictEqual(parsed.height, 768);
    assert.strictEqual(parsed.seed, 42);
  });

  void it("returns GenerateResponse on 200", async () => {
    mockFetchOnce(200, { job_id: "abc", status: "completed" });
    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "ok",
    });

    if ("code" in result) {
      assert.fail(`Expected success but got error: ${result.detail}`);
    }
    assert.strictEqual(result.job_id, "abc");
    assert.strictEqual(result.status, "completed");
  });

  void it("returns ApiError on 422", async () => {
    mockFetchOnce(422, { detail: "Invalid prompt" });
    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "validation_error");
    assert.strictEqual(result.detail, "Invalid prompt");
  });

  void it("returns ApiError on 500", async () => {
    mockFetchOnce(500, { error: { code: "model_busy", detail: "GPU full" } });
    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "error",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "model_busy");
  });

  void it("returns timeout on AbortError", async () => {
    mockFetchAbort();
    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "timeout",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "timeout");
  });

  void it("returns client_error on network failure (DNS/CORS/offline)", async () => {
    mockFetchNetworkError("fetch failed");
    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "network failure",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "client_error");
    assert.ok(result.detail.includes("fetch failed"));
  });

  void it("returns client_error on TypeError (non-Abort)", async () => {
    globalThis.fetch = async () => {
      // This is NOT an AbortError — e.g. CORS or JSON parse issue inside fetch
      throw new TypeError("Failed to fetch");
    };

    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "type error",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "client_error");
  });

  void it("timeout protects the body read (slow 200)", async () => {
    mockFetchSlow(100, 200, { job_id: "slow", status: "completed" });

    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "fast enough",
    });

    if ("code" in result) {
      assert.fail(`Expected success but got: ${result.code}`);
    }
    assert.strictEqual(result.job_id, "slow");
  });

  void it("timeout protects the body read (slow error body)", async () => {
    mockFetchSlow(100, 422, { detail: "Slow validation" });

    const result = await submitGenerate({
      workflow_name: "flux2_txt2img",
      prompt: "slow error",
    });

    assert.ok("code" in result);
    assert.strictEqual(result.code, "validation_error");
  });
});

// ─── fetchImageBinary ─────────────────────────────────────────

void describe("fetchImageBinary", () => {
  void it("GETs the correct URL", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response("binary", { status: 200 });
    };

    await fetchImageBinary("job-xyz");
    assert.strictEqual(calledUrl, "http://test-api.example.com/images/job-xyz");
  });

  void it("returns Response on 200", async () => {
    globalThis.fetch = async () =>
      new Response("binary-data", {
        status: 200,
        headers: { "content-type": "image/png" },
      });

    const result = await fetchImageBinary("ok-job");
    if ("code" in result) {
      assert.fail(`Expected Response but got error: ${result.detail}`);
    }
    assert.ok(result instanceof Response);
    assert.strictEqual(result.status, 200);
    assert.strictEqual(result.headers.get("content-type"), "image/png");
  });

  void it("returns Response on 404 (non-ok is still a Response)", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ code: "not_found", detail: "Missing" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    const result = await fetchImageBinary("missing-job");
    if ("code" in result) {
      assert.fail(`Expected Response even on 404, got ApiError`);
    }
    assert.strictEqual(result.status, 404);
  });

  void it("returns timeout on AbortError", async () => {
    mockFetchAbort();
    const result = await fetchImageBinary("abort-job");
    assert.ok("code" in result);
    assert.strictEqual(result.code, "timeout");
  });

  void it("returns client_error on network failure", async () => {
    mockFetchNetworkError("NetworkError: offline");
    const result = await fetchImageBinary("offline-job");
    assert.ok("code" in result);
    assert.strictEqual(result.code, "client_error");
    assert.ok(result.detail.includes("offline"));
  });
});

// ─── getWsUrl ──────────────────────────────────────────────────

void describe("getWsUrl", () => {
  void it("returns the correct WebSocket URL for a given jobId", () => {
    // env.apiBaseUrl = "http://test-api.example.com" (from before() hook)
    // env.wsBaseUrl  = "ws://test-api.example.com"
    const url = getWsUrl("123");
    assert.strictEqual(url, "ws://test-api.example.com/ws/generate/123");
  });
});
