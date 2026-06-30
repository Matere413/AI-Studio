// ─── Unit Tests: buildGenerateRequest ─────────────────────────
// Tests the request builder for each workflow variant.
// Pure function — no mocks needed.

import { describe, it } from "node:test";
import assert from "node:assert";
import { buildGenerateRequest, buildOrchestrateRequest } from "../build-generate-request.ts";

void describe("buildGenerateRequest", () => {
  // ── flux2_txt2img ───────────────────────────────────────────

  void describe("flux2_txt2img", () => {
    void it("creates a minimal request with prompt only", () => {
      const result = buildGenerateRequest("A cat", "flux2_txt2img");
      assert.strictEqual(result.workflow_name, "flux2_txt2img");
      assert.strictEqual(result.prompt, "A cat");
      assert.strictEqual((result as { use_turbo?: boolean }).use_turbo, undefined);
    });

    void it("includes use_turbo when set to true", () => {
      const result = buildGenerateRequest("A cat", "flux2_txt2img", {
        useTurbo: true,
      });
      assert.strictEqual(result.workflow_name, "flux2_txt2img");
      assert.strictEqual(result.prompt, "A cat");
      assert.strictEqual((result as { use_turbo?: boolean }).use_turbo, true);
    });

    void it("sets use_turbo to false when explicitly false", () => {
      const result = buildGenerateRequest("A cat", "flux2_txt2img", {
        useTurbo: false,
      });
      assert.strictEqual((result as { use_turbo?: boolean }).use_turbo, false);
    });

    void it("never includes image_base64, image_url, width, height, or seed", () => {
      const result = buildGenerateRequest("test", "flux2_txt2img", {
        useTurbo: true,
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.image_base64, undefined);
      assert.strictEqual(result.image_url, undefined);
      assert.strictEqual(result.width, undefined);
      assert.strictEqual(result.height, undefined);
      assert.strictEqual(result.seed, undefined);
    });
  });

  // ── flux2_editing ───────────────────────────────────────────

  void describe("flux2_editing", () => {
    void it("creates a request with prompt and image_base64", () => {
      const result = buildGenerateRequest("Edit this", "flux2_editing", {
        imageBase64: "iVBORw0KGgo...",
      });
      assert.strictEqual(result.workflow_name, "flux2_editing");
      assert.strictEqual(result.prompt, "Edit this");
      assert.strictEqual(
        (result as { image_base64: string }).image_base64,
        "iVBORw0KGgo...",
      );
    });

    void it("includes optional use_turbo", () => {
      const result = buildGenerateRequest("Edit this", "flux2_editing", {
        imageBase64: "iVBORw0KGgo...",
        useTurbo: true,
      });
      assert.strictEqual(
        (result as { image_base64: string }).image_base64,
        "iVBORw0KGgo...",
      );
      assert.strictEqual((result as { use_turbo?: boolean }).use_turbo, true);
    });

    void it("never includes width, height, or seed", () => {
      const result = buildGenerateRequest("Edit this", "flux2_editing", {
        imageBase64: "iVBORw0KGgo...",
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.width, undefined);
      assert.strictEqual(result.height, undefined);
      assert.strictEqual(result.seed, undefined);
    });
  });

  // ── identidad_gguf ──────────────────────────────────────────

  void describe("identidad_gguf", () => {
    void it("creates a minimal request with prompt and image_url", () => {
      const result = buildGenerateRequest("Portrait", "identidad_gguf", {
        imageUrl: "https://example.com/face.png",
      });
      assert.strictEqual(result.workflow_name, "identidad_gguf");
      assert.strictEqual(result.prompt, "Portrait");
      assert.strictEqual(
        (result as { image_url: string }).image_url,
        "https://example.com/face.png",
      );
    });

    void it("includes optional width, height, and seed", () => {
      const result = buildGenerateRequest("Portrait", "identidad_gguf", {
        imageUrl: "https://example.com/face.png",
        width: 1024,
        height: 768,
        seed: 42,
      }) as unknown as { width: number; height: number; seed: number };
      assert.strictEqual(result.width, 1024);
      assert.strictEqual(result.height, 768);
      assert.strictEqual(result.seed, 42);
    });

    void it("never includes image_base64 or use_turbo", () => {
      const result = buildGenerateRequest("Portrait", "identidad_gguf", {
        imageUrl: "https://example.com/face.png",
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.image_base64, undefined);
      assert.strictEqual(result.use_turbo, undefined);
    });
  });

  // ── Error cases — missing required params ───────────────────

  void describe("error cases", () => {
    void it("throws when imageBase64 is missing for flux2_editing", () => {
      assert.throws(
        () => buildGenerateRequest("Edit this", "flux2_editing"),
        { message: "imageBase64 or assetId is required for flux2_editing workflow" },
      );
    });

    void it("throws when imageBase64 is empty for flux2_editing", () => {
      assert.throws(
        () => buildGenerateRequest("Edit this", "flux2_editing", {
          imageBase64: "",
        }),
        { message: "imageBase64 or assetId is required for flux2_editing workflow" },
      );
    });

    void it("throws when imageBase64 is undefined for flux2_editing", () => {
      assert.throws(
        () =>
          buildGenerateRequest("Edit this", "flux2_editing", {
            imageBase64: undefined,
          }),
        { message: "imageBase64 or assetId is required for flux2_editing workflow" },
      );
    });

    void it("throws when imageUrl is missing for identidad_gguf", () => {
      assert.throws(
        () => buildGenerateRequest("Portrait", "identidad_gguf"),
        { message: "imageUrl is required for identidad_gguf workflow" },
      );
    });

    void it("throws when imageUrl is empty for identidad_gguf", () => {
      assert.throws(
        () => buildGenerateRequest("Portrait", "identidad_gguf", {
          imageUrl: "",
        }),
        { message: "imageUrl is required for identidad_gguf workflow" },
      );
    });

    void it("throws when imageUrl is undefined for identidad_gguf", () => {
      assert.throws(
        () =>
          buildGenerateRequest("Portrait", "identidad_gguf", {
            imageUrl: undefined,
          }),
        { message: "imageUrl is required for identidad_gguf workflow" },
      );
    });

    void it("still accepts valid flux2_editing with imageBase64", () => {
      const result = buildGenerateRequest("Edit", "flux2_editing", {
        imageBase64: "iVBORw0KGgo...",
      });
      assert.strictEqual(result.workflow_name, "flux2_editing");
    });

    void it("still accepts valid identidad_gguf with imageUrl", () => {
      const result = buildGenerateRequest("Portrait", "identidad_gguf", {
        imageUrl: "https://example.com/face.png",
      });
      assert.strictEqual(result.workflow_name, "identidad_gguf");
    });
  });

  // ── Edge Cases ──────────────────────────────────────────────

  void describe("edge cases", () => {
    void it("accepts empty prompt (validation is separate)", () => {
      const result = buildGenerateRequest("", "flux2_txt2img");
      assert.strictEqual(result.workflow_name, "flux2_txt2img");
      assert.strictEqual(result.prompt, "");
    });

    void it("works with undefined params", () => {
      const result = buildGenerateRequest("test", "flux2_txt2img", undefined);
      assert.strictEqual(result.workflow_name, "flux2_txt2img");
      assert.strictEqual(result.prompt, "test");
    });

    void it("ignores irrelevant params for flux2_txt2img", () => {
      const result = buildGenerateRequest("test", "flux2_txt2img", {
        imageBase64: "abc",
        imageUrl: "http://x.com/y.png",
        width: 512,
        seed: 7,
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.workflow_name, "flux2_txt2img");
      assert.strictEqual(result.prompt, "test");
      assert.strictEqual(result.image_base64, undefined);
      assert.strictEqual(result.image_url, undefined);
      assert.strictEqual(result.width, undefined);
      assert.strictEqual(result.seed, undefined);
    });

    void it("ignores irrelevant params for flux2_editing", () => {
      const result = buildGenerateRequest("test", "flux2_editing", {
        imageBase64: "iVBORw0KGgo...",
        width: 512,
        height: 512,
        seed: 7,
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.workflow_name, "flux2_editing");
      assert.strictEqual(result.image_base64, "iVBORw0KGgo...");
      assert.strictEqual(result.width, undefined);
      assert.strictEqual(result.height, undefined);
      assert.strictEqual(result.seed, undefined);
    });

    void it("ignores irrelevant params for identidad_gguf", () => {
      const result = buildGenerateRequest("test", "identidad_gguf", {
        imageUrl: "https://example.com/face.png",
        useTurbo: true,
        imageBase64: "abc",
      }) as unknown as Record<string, unknown>;
      assert.strictEqual(result.workflow_name, "identidad_gguf");
      assert.strictEqual(result.image_url, "https://example.com/face.png");
      assert.strictEqual(result.use_turbo, undefined);
      assert.strictEqual(result.image_base64, undefined);
    });
  });
});

void describe("buildOrchestrateRequest", () => {
  void it("builds a prompt-first request with selected asset identifiers", () => {
    const result = buildOrchestrateRequest("Create a product hero", {
      selectedAssetIds: ["asset-product", "asset-background"],
    });

    assert.deepStrictEqual(result, {
      prompt: "Create a product hero",
      selected_asset_ids: ["asset-product", "asset-background"],
    });
  });

  void it("omits workflow_hint and use_turbo when not provided", () => {
    const result = buildOrchestrateRequest(
      "Preserve this person's identity",
      { selectedAssetIds: ["asset-face"] },
    ) as unknown as Record<string, unknown>;

    assert.strictEqual(result.prompt, "Preserve this person's identity");
    assert.deepStrictEqual(result.selected_asset_ids, ["asset-face"]);
    assert.strictEqual(result.workflow_hint, undefined);
    assert.strictEqual(result.use_turbo, undefined);
    assert.strictEqual(result.image_url, undefined);
    assert.strictEqual(result.width, undefined);
    assert.strictEqual(result.height, undefined);
    assert.strictEqual(result.seed, undefined);
  });

  void it("includes workflow_hint and use_turbo when provided", () => {
    const result = buildOrchestrateRequest("Generate a product shot", {
      selectedAssetIds: ["asset-1"],
      workflowHint: "flux2_txt2img",
      useTurbo: true,
    });

    assert.strictEqual(result.prompt, "Generate a product shot");
    assert.deepStrictEqual(result.selected_asset_ids, ["asset-1"]);
    assert.strictEqual(result.workflow_hint, "flux2_txt2img");
    assert.strictEqual(result.use_turbo, true);
  });

  void it("includes workspace context only when keys are provided", () => {
    const withContext = buildOrchestrateRequest("Generate an ad", {
      selectedAssetIds: [],
      workspaceContext: { project_id: "project-1" },
    });
    const withoutContext = buildOrchestrateRequest("Generate an ad", {
      selectedAssetIds: [],
      workspaceContext: {},
    });

    assert.deepStrictEqual(withContext.workspace_context, {
      project_id: "project-1",
    });
    assert.strictEqual(withoutContext.workspace_context, undefined);
  });
});
