// ─── Unit Tests: API Client ──────────────────────────────────
// Tests submitGenerate and fetchImageBinary with mocked fetch.
// Uses Node built-in test runner — no Jest dependency.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import {
  submitGenerate,
  submitOrchestrate,
  fetchImageBinary,
  getWsUrl,
  fetchWithSession,
  type FetchWithSessionOptions,
} from "../api-client.ts";
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

void describe("submitOrchestrate", () => {
  void it("POSTs prompt-first requests to the orchestration endpoint", async () => {
    let calledUrl = "";
    let sentBody = "";
    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      sentBody = (init as RequestInit).body as string;
      return new Response(
        JSON.stringify({
          outcome: "job_started",
          job_id: "job-1",
          status: "pending",
          stages: [{ name: "planning", status: "completed" }],
        }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    };

    const result = await submitOrchestrate({
      prompt: "Make a clean product shot",
      selected_asset_ids: ["asset-1"],
    });

    assert.strictEqual(calledUrl, "http://test-api.example.com/generate/orchestrate");
    assert.deepStrictEqual(JSON.parse(sentBody), {
      prompt: "Make a clean product shot",
      selected_asset_ids: ["asset-1"],
    });
    assert.strictEqual(result.outcome, "job_started");
    assert.strictEqual(result.job_id, "job-1");
  });

  void it("normalizes clarification responses without creating a client error", async () => {
    mockFetchOnce(200, {
      outcome: "clarification_required",
      question: "Which product should I improve?",
      stages: [{ name: "planning", status: "blocked" }],
    });

    const result = await submitOrchestrate({
      prompt: "Make it better",
      selected_asset_ids: [],
    });

    assert.strictEqual(result.outcome, "clarification_required");
    assert.strictEqual(result.question, "Which product should I improve?");
    assert.deepStrictEqual(result.stages, [
      { name: "planning", status: "blocked" },
    ]);
  });

  void it("normalizes missing-asset guidance responses", async () => {
    mockFetchOnce(200, {
      outcome: "missing_asset",
      missing_roles: ["identity_reference"],
      guidance: "Upload or select an identity reference before generating.",
      stages: [
        { name: "planning", status: "completed" },
        { name: "validating_assets", status: "blocked" },
      ],
    });

    const result = await submitOrchestrate({
      prompt: "Preserve this person's identity",
      selected_asset_ids: [],
    });

    assert.strictEqual(result.outcome, "missing_asset");
    assert.deepStrictEqual(result.missing_roles, ["identity_reference"]);
    assert.ok(result.guidance?.includes("Upload or select"));
  });

  void it("returns an orchestration error outcome for non-2xx backend errors", async () => {
    mockFetchOnce(422, {
      outcome: "error",
      error_code: "unsupported_workflow",
      error_detail: "Workflow is not supported",
      stages: [{ name: "planning", status: "blocked" }],
    });

    const result = await submitOrchestrate({
      prompt: "Edit this unsupported way",
      selected_asset_ids: ["asset-1"],
    });

    assert.strictEqual(result.outcome, "error");
    assert.strictEqual(result.error_code, "unsupported_workflow");
    assert.strictEqual(result.error_detail, "Workflow is not supported");
  });

  void it("rejects malformed 2xx job_started responses without a job_id", async () => {
    mockFetchOnce(202, {
      outcome: "job_started",
      status: "pending",
      stages: [{ name: "planning", status: "completed" }],
    });

    const result = await submitOrchestrate({
      prompt: "Generate a poster",
      selected_asset_ids: [],
    });

    assert.strictEqual(result.outcome, "error");
    assert.strictEqual(result.error_code, "invalid_orchestration_response");
    assert.strictEqual(result.error_detail, "Orchestration response was invalid");
  });

  void it("sanitizes raw backend detail from malformed successful responses", async () => {
    mockFetchOnce(200, {
      outcome: "error",
      error_code: "planner_provider_invalid_response",
      error_detail: "Traceback: provider returned secret-key-123 and raw schema text",
      stages: [{ name: "planning", status: "blocked" }],
    });

    const result = await submitOrchestrate({
      prompt: "Create a product shot",
      selected_asset_ids: [],
    });

    assert.strictEqual(result.outcome, "error");
    assert.strictEqual(result.error_code, "planner_provider_invalid_response");
    assert.strictEqual(result.error_detail, "Planning service returned an invalid response");
  });
});

// ─── Session Cookie Sync ──────────────────────────────────────

void describe("session cookie sync", () => {
  const ORIGINAL_WINDOW = globalThis.window;
  const ORIGINAL_DOCUMENT = globalThis.document;
  const ORIGINAL_LOCAL_STORAGE = globalThis.localStorage;

  before(() => {
    let store = new Map<string, string>();

    globalThis.window = {} as Window & typeof globalThis.window;
    globalThis.document = { cookie: "" } as Document;
    globalThis.localStorage = {
      getItem(key: string) {
        return store.get(key) ?? null;
      },
      setItem(key: string, value: string) {
        store.set(key, value);
      },
      removeItem(key: string) {
        store.delete(key);
      },
      clear() {
        store = new Map<string, string>();
      },
      key(index: number) {
        return Array.from(store.keys())[index] ?? null;
      },
      get length() {
        return store.size;
      },
    } as Storage;
  });

  after(() => {
    globalThis.window = ORIGINAL_WINDOW;
    globalThis.document = ORIGINAL_DOCUMENT;
    globalThis.localStorage = ORIGINAL_LOCAL_STORAGE;
  });

  void it("mirrors an existing localStorage session ID into document.cookie", async () => {
    let sentHeaders: Record<string, string> = {};
    globalThis.localStorage.setItem("ai-studio-session-id", "session-cookie-123");
    globalThis.fetch = async (_url, init) => {
      sentHeaders = (init as RequestInit).headers as Record<string, string>;
      return new Response(JSON.stringify({ job_id: "abc", status: "pending" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await submitGenerate({ workflow_name: "flux2_txt2img", prompt: "cookie sync" });

    assert.strictEqual(sentHeaders["X-Session-ID"], "session-cookie-123");
    assert.ok(document.cookie.includes("ai-studio-session-id=session-cookie-123"));
    assert.ok(document.cookie.includes("Path=/"));
    assert.ok(document.cookie.includes("SameSite=Lax"));
    assert.ok(!document.cookie.includes("HttpOnly"));
  });

  void it("submitOrchestrate sends X-Session-ID from localStorage session", async () => {
    globalThis.localStorage.setItem("ai-studio-session-id", "orch-session-456");

    let sentSessionId = "";
    globalThis.fetch = async (_url, init) => {
      const headers = (init as RequestInit).headers as Record<string, string>;
      sentSessionId = headers["X-Session-ID"] ?? "";
      return new Response(
        JSON.stringify({
          outcome: "job_started",
          job_id: "job-2",
          status: "pending",
          stages: [{ name: "planning", status: "completed" }],
        }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    };

    await submitOrchestrate({
      prompt: "Test session header",
      selected_asset_ids: [],
    });

    assert.strictEqual(sentSessionId, "orch-session-456");
  });

  void it("submitOrchestrate syncs the session cookie to document.cookie", async () => {
    globalThis.localStorage.setItem("ai-studio-session-id", "cookie-sync-789");

    globalThis.fetch = async (_url, init) => {
      return new Response(
        JSON.stringify({
          outcome: "job_started",
          job_id: "job-3",
          status: "pending",
          stages: [{ name: "planning", status: "completed" }],
        }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    };

    await submitOrchestrate({
      prompt: "Test cookie sync",
      selected_asset_ids: [],
    });

    // document.cookie is set as a flat string (mock document).
    // Check the full cookie string for the expected attributes.
    assert.ok(document.cookie.includes("ai-studio-session-id=cookie-sync-789"));
    assert.ok(document.cookie.includes("Path=/"));
    assert.ok(document.cookie.includes("SameSite=Lax"));
  });

  void it("submitOrchestrate targets /generate/orchestrate endpoint", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response(
        JSON.stringify({
          outcome: "job_started",
          job_id: "job-url",
          status: "pending",
          stages: [{ name: "planning", status: "completed" }],
        }),
        { status: 202, headers: { "content-type": "application/json" } },
      );
    };

    await submitOrchestrate({
      prompt: "Check URL",
      selected_asset_ids: [],
    });

    assert.strictEqual(
      calledUrl,
      "http://test-api.example.com/generate/orchestrate",
    );
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

// ─── fetchWithSession ─────────────────────────────────────────

void describe("fetchWithSession", () => {
  void it("GETs the correct URL", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/projects");
    assert.strictEqual(
      calledUrl,
      "http://test-api.example.com/projects",
    );
  });

  void it("passes custom headers through to fetch", async () => {
    let sentHeaders: Record<string, string> = {};
    globalThis.fetch = async (_url, init) => {
      sentHeaders = (init as RequestInit).headers as Record<
        string,
        string
      >;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/projects", {
      headers: { "X-Custom": "test-value" },
    });
    assert.strictEqual(sentHeaders["X-Custom"], "test-value");
  });

  void it("supports POST with JSON body", async () => {
    let sentMethod = "";
    let sentBody = "";
    let sentContentType = "";
    globalThis.fetch = async (_url, init) => {
      const r = init as RequestInit;
      sentMethod = r.method ?? "GET";
      sentBody = r.body as string;
      sentContentType = (r.headers as Record<string, string>)[
        "Content-Type"
      ];
      return new Response(JSON.stringify({ id: "p1" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/projects", {
      method: "POST",
      body: JSON.stringify({ name: "Test" }),
    });
    assert.strictEqual(sentMethod, "POST");
    assert.strictEqual(sentContentType, "application/json");
    assert.strictEqual(sentBody, JSON.stringify({ name: "Test" }));
  });

  void it("supports PATCH method", async () => {
    let sentMethod = "";
    globalThis.fetch = async (_url, init) => {
      sentMethod = (init as RequestInit).method ?? "GET";
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/assets/1/finalize", {
      method: "PATCH",
    });
    assert.strictEqual(sentMethod, "PATCH");
  });

  void it("supports DELETE method", async () => {
    let sentMethod = "";
    globalThis.fetch = async (_url, init) => {
      sentMethod = (init as RequestInit).method ?? "GET";
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/assets/1", {
      method: "DELETE",
    });
    assert.strictEqual(sentMethod, "DELETE");
  });

  void it("defaults to credentials: 'include' so cross-origin auth cookies flow", async () => {
    let sentCredentials: RequestCredentials | undefined;
    globalThis.fetch = async (_url, init) => {
      sentCredentials = (init as RequestInit).credentials;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/projects");
    assert.strictEqual(
      sentCredentials,
      "include",
      "fetchWithSession MUST default credentials to 'include' so the auth cookies (ai-studio-auth / ai-studio-refresh) are sent on every call — non-auth callers like createProject() rely on this default",
    );
  });

  void it("honours an explicit credentials: 'omit' override", async () => {
    let sentCredentials: RequestCredentials | undefined;
    globalThis.fetch = async (_url, init) => {
      sentCredentials = (init as RequestInit).credentials;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/projects", {
      credentials: "omit",
    });
    assert.strictEqual(sentCredentials, "omit");
  });

  void it("returns Response on 200", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    const res: Response = await fetchWithSession(
      "http://test-api.example.com/projects",
    );
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.ok, true);
  });

  void it("returns Response on 404 (non-ok is still a Response)", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ error: "not_found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    const res = await fetchWithSession(
      "http://test-api.example.com/projects/404",
    );
    assert.strictEqual(res.status, 404);
    assert.strictEqual(res.ok, false);
  });

  void it("throws ApiError on network failure", async () => {
    globalThis.fetch = async () => {
      throw new TypeError("fetch failed");
    };

    try {
      await fetchWithSession("http://test-api.example.com/projects");
      assert.fail("Expected ApiError to be thrown");
    } catch (err) {
      const apiErr = err as { code: string; detail: string };
      assert.strictEqual(apiErr.code, "client_error");
    }
  });

  void it("throws ApiError with timeout code on AbortError", async () => {
    globalThis.fetch = async () => {
      throw new DOMException("The operation was aborted", "AbortError");
    };

    try {
      await fetchWithSession("http://test-api.example.com/projects");
      assert.fail("Expected ApiError to be thrown");
    } catch (err) {
      const apiErr = err as { code: string; detail: string };
      assert.strictEqual(apiErr.code, "timeout");
    }
  });

  void it("custom headers are passed alongside Content-Type", async () => {
    let sentHeaders: Record<string, string> = {};
    globalThis.fetch = async (_url, init) => {
      sentHeaders = (init as RequestInit).headers as Record<
        string,
        string
      >;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/assets", {
      method: "POST",
      body: JSON.stringify({ name: "test" }),
      headers: { "X-Custom": "test-value" },
    });
    assert.strictEqual(sentHeaders["X-Custom"], "test-value");
    assert.strictEqual(sentHeaders["Content-Type"], "application/json");
  });

  void it("does not override explicit Content-Type", async () => {
    let sentContentType = "";
    globalThis.fetch = async (_url, init) => {
      const headers = (init as RequestInit).headers as Record<
        string,
        string
      >;
      sentContentType = headers["Content-Type"] ?? "";
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    await fetchWithSession("http://test-api.example.com/upload", {
      method: "PUT",
      body: new Blob(["binary"]),
      headers: { "Content-Type": "image/webp" },
    });
    assert.strictEqual(sentContentType, "image/webp");
  });

  // ─── External AbortSignal (C4): caller cancellation aborts the fetch ───

  void it("external signal aborts an in-flight fetch (aborted ApiError)", async () => {
    // A slow fetch that respects the abort signal — when the external
    // signal aborts, the fetch rejects and fetchWithSession surfaces an
    // `aborted` ApiError (distinct from the internal timeout's `timeout`).
    globalThis.fetch = async (_input, init?: RequestInit) => {
      await new Promise((_resolve, reject) => {
        const signal = init?.signal;
        if (signal) {
          if (signal.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }
          signal.addEventListener(
            "abort",
            () => reject(new DOMException("aborted", "AbortError")),
            { once: true },
          );
        }
      });
      return new Response("{}", { status: 200 });
    };

    const controller = new AbortController();
    const fetchPromise = fetchWithSession("http://test-api.example.com/projects", {
      signal: controller.signal,
      timeoutMs: 10_000,
    });
    // Abort after a short delay — the fetch is in-flight.
    setTimeout(() => controller.abort(), 10);
    try {
      await fetchPromise;
      assert.fail("Expected aborted ApiError to be thrown");
    } catch (err) {
      const apiErr = err as { code: string; detail: string };
      assert.strictEqual(
        apiErr.code,
        "aborted",
        "an external-signal abort MUST surface an `aborted` ApiError (distinct from the internal timeout)",
      );
    }
  });

  void it("already-aborted external signal aborts before the fetch starts", async () => {
    // When the external signal is already aborted at call time, the fetch
    // is aborted immediately (the internal controller aborts before
    // awaiting fetch).
    let fetchCalled = false;
    globalThis.fetch = async () => {
      fetchCalled = true;
      throw new DOMException("aborted", "AbortError");
    };

    const controller = new AbortController();
    controller.abort();
    try {
      await fetchWithSession("http://test-api.example.com/projects", {
        signal: controller.signal,
        timeoutMs: 10_000,
      });
      assert.fail("Expected aborted ApiError to be thrown");
    } catch (err) {
      const apiErr = err as { code: string; detail: string };
      assert.strictEqual(apiErr.code, "aborted", "a pre-aborted signal MUST surface an `aborted` ApiError");
    }
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
