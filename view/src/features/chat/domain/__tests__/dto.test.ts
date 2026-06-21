// ─── Unit Tests: Chat Domain DTOs ────────────────────────────
// Tests the per-workflow validation rules for GenerateRequest.

import { describe, it } from "node:test";
import assert from "node:assert";
import { validateRequest } from "../dto.ts";
import type {
  Flux2Txt2ImgRequest,
  Flux2EditingRequest,
  IdentidadGgufRequest,
  GenerateRequest,
} from "../dto.ts";

void describe("validateRequest", () => {
  // ── flux2_txt2img ─────────────────────────────────────────

  void describe("flux2_txt2img", () => {
    void it("accepts minimal valid request", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_txt2img",
        prompt: "A cat on a couch",
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
      assert.deepStrictEqual(result.errors, []);
    });

    void it("accepts request with optional use_turbo", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_txt2img",
        prompt: "A dog in a park",
        use_turbo: true,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("rejects empty prompt", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_txt2img",
        prompt: "",
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("prompt")));
    });

    void it("rejects image_base64 field", () => {
      // Simulate an object that carries a field it shouldn't
      const req = {
        workflow_name: "flux2_txt2img",
        prompt: "test",
        image_base64: "abc123",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("image_base64")),
      );
    });

    void it("rejects width and height fields", () => {
      const req = {
        workflow_name: "flux2_txt2img",
        prompt: "test",
        width: 1024,
        height: 768,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("width")));
      assert.ok(result.errors.some((e) => e.includes("height")));
    });

    void it("rejects image_url field", () => {
      const req = {
        workflow_name: "flux2_txt2img",
        prompt: "test",
        image_url: "https://example.com/img.png",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("image_url")));
    });

    void it("rejects seed field (identidad_gguf only)", () => {
      const req = {
        workflow_name: "flux2_txt2img",
        prompt: "test",
        seed: 42,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("seed")));
    });
  });

  // ── flux2_editing ─────────────────────────────────────────

  void describe("flux2_editing", () => {
    void it("accepts valid editing request with image_base64", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_editing",
        prompt: "Make it night time",
        image_base64: "iVBORw0KGgo...",
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("accepts optional use_turbo (seed is identidad_gguf only)", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_editing",
        prompt: "Add a sunset",
        image_base64: "iVBORw0KGgo...",
        use_turbo: false,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("rejects missing image_base64", () => {
      const req = {
        workflow_name: "flux2_editing",
        prompt: "Edit this",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("image_base64")),
      );
    });

    void it("rejects empty image_base64", () => {
      const req: GenerateRequest = {
        workflow_name: "flux2_editing",
        prompt: "Edit this",
        image_base64: "",
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("image_base64")),
      );
    });

    void it("rejects width field (per spec)", () => {
      const req = {
        workflow_name: "flux2_editing",
        prompt: "Edit this",
        image_base64: "iVBORw0KGgo...",
        width: 1024,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("width")));
    });

    void it("rejects height field (per spec)", () => {
      const req = {
        workflow_name: "flux2_editing",
        prompt: "Edit this",
        image_base64: "iVBORw0KGgo...",
        height: 768,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("height")));
    });

    void it("rejects seed field (identidad_gguf only)", () => {
      const req = {
        workflow_name: "flux2_editing",
        prompt: "Edit this",
        image_base64: "iVBORw0KGgo...",
        seed: 42,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("seed")));
    });
  });

  // ── identidad_gguf ────────────────────────────────────────

  void describe("identidad_gguf", () => {
    void it("accepts minimal valid request with image_url", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Generate from reference",
        image_url: "https://example.com/face.png",
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("accepts optional width, height, seed", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Full body portrait",
        image_url: "https://example.com/face.png",
        width: 1024,
        height: 768,
        seed: 7,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("rejects missing image_url", () => {
      const req = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("image_url")));
    });

    void it("rejects empty image_url", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "",
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("image_url")));
    });

    void it("rejects image_base64 field", () => {
      const req = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        image_base64: "abc123",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("image_base64")),
      );
    });

    void it("rejects use_turbo (identidad_gguf has no turbo mode)", () => {
      const req = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        use_turbo: true,
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("use_turbo")),
      );
    });

    void it("rejects invalid image_url (non-http, non-data-uri)", () => {
      const req = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "ftp://bad/protocol.png",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(
        result.errors.some((e) => e.includes("image_url")),
      );
    });

    void it("accepts data: URI as valid image_url", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAE=",
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    // ── Geometry Validation ─────────────────────────────────

    void it("accepts valid width/height at boundary (256)", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 256,
        height: 256,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("accepts valid width/height at boundary (2048)", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 2048,
        height: 2048,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("accepts valid width/height multiples of 64", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 1024,
        height: 768,
      };
      const result = validateRequest(req);
      assert.ok(result.valid);
    });

    void it("rejects width below 256", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 128,
        height: 512,
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("width")));
    });

    void it("rejects height above 2048", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 1024,
        height: 4096,
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("height")));
    });

    void it("rejects width not a multiple of 64", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 300,   // 300 ÷ 64 = 4.6875 — in range (256-2048) but not a multiple of 64
        height: 512,
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("multiple of 64")));
    });

    void it("rejects height not a multiple of 64", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 512,
        height: 300,  // 300 ÷ 64 = 4.6875 — in range (256-2048) but not a multiple of 64
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("multiple of 64")));
    });

    void it("rejects total area exceeding 4,194,304 pixels", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        // 2048 × 2048 = 4,194,304 — one pixel over would be too much
        width: 2048,
        height: 2049,
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.some((e) => e.includes("area")));
    });

    void it("rejects multiple geometry violations simultaneously", () => {
      const req: GenerateRequest = {
        workflow_name: "identidad_gguf",
        prompt: "Portrait",
        image_url: "https://example.com/face.png",
        width: 3000,     // > 2048
        height: 63,      // < 256 and not multiple of 64
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      // Should have at least 2 geometry errors
      const geoErrors = result.errors.filter(
        (e) => e.includes("width") || e.includes("height"),
      );
      assert.ok(geoErrors.length >= 2);
    });
  });

  // ── Edge Cases ─────────────────────────────────────────────

  void describe("edge cases", () => {
    void it("accumulates multiple errors", () => {
      const req = {
        workflow_name: "flux2_txt2img" as const,
        prompt: "",
        image_base64: "abc",
        width: 512,
        height: 512,
        image_url: "http://x.com/y.png",
      };
      const result = validateRequest(req);
      assert.ok(!result.valid);
      // Should have at least 4 errors: empty prompt + 3 prohibited fields
      assert.ok(result.errors.length >= 4);
    });

    void it("empty body-like object with workflow_name only", () => {
      const req = {
        workflow_name: "flux2_editing",
      } as GenerateRequest;
      const result = validateRequest(req);
      assert.ok(!result.valid);
      assert.ok(result.errors.length >= 2); // missing prompt + missing image_base64
    });
  });
});
