// ─── Unit Tests: root layout metadata ────────────────────────────
// Asserts the root `layout.tsx` exports `metadata.title === "AI Studio"`
// (spec: "Root Layout Metadata Title"). Uses the transpile + CJS
// harness (shared with auth-forms.test.ts) because `layout.tsx`
// imports `./globals.css` and `next` types that bare Node ESM cannot
// load. The CSS and AuthProvider imports are stubbed so the module's
// `metadata` export is reachable without a real DOM or Next runtime.

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";

const require = createRequire(import.meta.url);

function transpileModule(filePath: string): string {
  const source = readFileSync(filePath, "utf8");
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
  }).outputText;
}

function loadModule(file: string, requireOverrides: Record<string, unknown> = {}) {
  const js = transpileModule(join(process.cwd(), file));
  const cjsModule = { exports: {} as Record<string, unknown> };
  const customRequire = (id: string) => {
    if (id === "react") return React;
    if (id === "react/jsx-runtime") return require("react/jsx-runtime");
    if (requireOverrides[id] !== undefined) return requireOverrides[id];
    return require(id);
  };
  new Function("require", "module", "exports", js)(customRequire, cjsModule, cjsModule.exports);
  return cjsModule.exports;
}

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});
after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
});

void describe("root layout metadata", () => {
  void it("exports metadata.title === 'AI Studio'", () => {
    const mod = loadModule("src/app/layout.tsx", {
      "./globals.css": {},
      "@/features/auth/application/auth-provider": {
        AuthProvider: ({ children }: { children: React.ReactNode }) => children,
      },
    });
    const metadata = (mod as { metadata?: { title?: string } }).metadata;
    assert.ok(metadata, "layout MUST export a `metadata` object");
    assert.strictEqual(
      metadata?.title,
      "AI Studio",
      `metadata.title MUST read 'AI Studio'; got: ${JSON.stringify(metadata?.title)}`,
    );
  });
});