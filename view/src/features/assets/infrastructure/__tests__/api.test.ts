// ─── Unit Tests: Assets API Client ──────────────────────────────
// Tests the assets feature API module: project listing, upload
// ticket request, finalize, and delete.
//
// These tests will FAIL (RED) until api.ts is created.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";

// NOTE: These imports will fail until api.ts is created (RED phase)
import {
  createProject,
  fetchProjects,
  requestUploadTicket,
  finalizeAsset,
  deleteAsset,
} from "../api.ts";

// ─── Setup / Teardown ─────────────────────────────────────────

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  globalThis.fetch = undefined as unknown as typeof globalThis.fetch;
});

// ─── fetchProjects ───────────────────────────────────────────

void describe("fetchProjects", () => {
  void it("GETs /projects and returns parsed response", async () => {
    let calledUrl = "";
    globalThis.fetch = async (url) => {
      calledUrl = url.toString();
      return new Response(
        JSON.stringify([
          { id: "p1", name: "Project A" },
        ]),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    const result = await fetchProjects();
    assert.strictEqual(calledUrl, "http://test-api.example.com/projects");
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].id, "p1");
    assert.strictEqual(result[0].name, "Project A");
  });

  void it("returns empty array when no projects exist", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    const result = await fetchProjects();
    assert.deepStrictEqual(result, []);
  });
});

// ─── createProject ──────────────────────────────────────────

void describe("createProject", () => {
  void it("POSTs to /projects with name in JSON body and returns project", async () => {
    let calledUrl = "";
    let sentMethod = "";
    let sentBody = "";
    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      const r = init as RequestInit;
      sentMethod = r.method ?? "GET";
      sentBody = r.body as string;
      return new Response(
        JSON.stringify({
          id: "p1",
          name: "My Project",
          session_id: "sess-1",
          created_at: "2026-01-01T00:00:00Z",
          assets: [],
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    };

    const result = await createProject("My Project");
    assert.strictEqual(calledUrl, "http://test-api.example.com/projects");
    assert.strictEqual(sentMethod, "POST");
    assert.strictEqual(sentBody, JSON.stringify({ name: "My Project" }));
    assert.strictEqual(result.id, "p1");
    assert.strictEqual(result.name, "My Project");
  });

  void it("throws on non-ok response", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ error: { code: "validation_error", detail: "Name too short" } }), {
        status: 422,
        headers: { "content-type": "application/json" },
      });

    await assert.rejects(
      () => createProject(""),
      { code: "validation_error" },
    );
  });

  void it("propagates error detail for UI error display", async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({ error: { code: "server_error", detail: "Internal error creating project" } }),
        { status: 500, headers: { "content-type": "application/json" } },
      );

    let caught: unknown;
    try {
      await createProject("fail");
    } catch (err) {
      caught = err;
    }

    assert.ok(caught, "Expected an error to be thrown");
    const apiErr = caught as { code: string; detail: string };
    assert.strictEqual(apiErr.code, "server_error");
    assert.strictEqual(
      apiErr.detail,
      "Internal error creating project",
      "Error detail must propagate to UI",
    );
  });
});

// ─── requestUploadTicket ──────────────────────────────────────

void describe("requestUploadTicket", () => {
  void it("POSTs to /projects/{id}/upload-ticket with JSON body", async () => {
    let calledUrl = "";
    let sentMethod = "";
    let sentBody = "";
    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      const r = init as RequestInit;
      sentMethod = r.method ?? "GET";
      sentBody = r.body as string;
      return new Response(
        JSON.stringify({
          asset_id: "a1",
          presigned_url: "https://r2.example.com/upload",
          r2_key: "projects/p1/a1.webp",
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    const result = await requestUploadTicket("p1", "test.webp", "image/webp");
    assert.strictEqual(
      calledUrl,
      "http://test-api.example.com/projects/p1/upload-ticket",
    );
    assert.strictEqual(sentMethod, "POST");
    assert.strictEqual(sentBody, JSON.stringify({ asset_name: "test.webp", content_type: "image/webp" }));
    assert.strictEqual(result.asset_id, "a1");
    assert.strictEqual(result.presigned_url, "https://r2.example.com/upload");
    assert.strictEqual(result.r2_key, "projects/p1/a1.webp");
  });

  void it("throws on non-ok response", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ error: { code: "not_found", detail: "Project not found" } }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    await assert.rejects(
      () => requestUploadTicket("nonexistent", "f.webp", "image/webp"),
      { code: "not_found" },
    );
  });
});

// ─── finalizeAsset ────────────────────────────────────────────

void describe("finalizeAsset", () => {
  void it("PATCHes /assets/{id}/finalize", async () => {
    let calledUrl = "";
    let sentMethod = "";
    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      sentMethod = (init as RequestInit).method ?? "GET";
      return new Response(
        JSON.stringify({ id: "a1", status: "ready" }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    const result = await finalizeAsset("a1");
    assert.strictEqual(
      calledUrl,
      "http://test-api.example.com/assets/a1/finalize",
    );
    assert.strictEqual(sentMethod, "PATCH");
    assert.strictEqual(result.id, "a1");
  });

  void it("throws on non-ok response", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ error: { code: "not_found", detail: "Asset not found" } }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    await assert.rejects(
      () => finalizeAsset("nonexistent"),
      { code: "not_found" },
    );
  });
});

// ─── deleteAsset ────────────────────────────────────────────

void describe("deleteAsset", () => {
  void it("DELETEs /assets/{id}", async () => {
    let calledUrl = "";
    let sentMethod = "";
    globalThis.fetch = async (url, init) => {
      calledUrl = url.toString();
      sentMethod = (init as RequestInit).method ?? "GET";
      return new Response(null, { status: 204 });
    };

    await deleteAsset("a1");
    assert.strictEqual(calledUrl, "http://test-api.example.com/assets/a1");
    assert.strictEqual(sentMethod, "DELETE");
  });

  void it("throws on non-ok response", async () => {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ error: { code: "not_found", detail: "Asset not found" } }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });

    await assert.rejects(
      () => deleteAsset("nonexistent"),
      { code: "not_found" },
    );
  });
});
