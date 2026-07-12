import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

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

function loadModule(
  js: string,
  requireOverrides: Record<string, unknown>,
): { exports: Record<string, unknown> } {
  const cjsModule = { exports: {} as Record<string, unknown> };
  const customRequire = (id: string) => {
    if (id === "react") return React;
    if (id === "react/jsx-runtime") return require("react/jsx-runtime");
    if (requireOverrides[id] !== undefined) return requireOverrides[id];
    return require(id);
  };
  new Function("require", "module", "exports", js)(customRequire, cjsModule, cjsModule.exports);
  return cjsModule;
}

function loadBanner() {
  const js = transpileModule(
    join(
      process.cwd(),
      "src/features/auth/presentation/components/BootstrapRetryBanner.tsx",
    ),
  );
  return loadModule(js, {}).exports;
}

type BannerProps = { shown: boolean; onRetry: () => void; retrying?: boolean; error?: string | null };
const Banner = () => (loadBanner() as { BootstrapRetryBanner: React.ComponentType<BannerProps> }).BootstrapRetryBanner;

async function render(props: BannerProps) {
  let renderer!: TestRenderer.ReactTestRenderer;
  await act(async () => { renderer = TestRenderer.create(React.createElement(Banner(), props)); });
  return renderer;
}

void describe("BootstrapRetryBanner", () => {
  void it("hides when not retryable", async () => {
    const root = (await render({ shown: false, onRetry: () => {} })).root;
    assert.strictEqual(root.findAllByProps({ "aria-label": "Retry connection" }).length, 0);
  });

  void it("wires retry and reflects retrying state", async () => {
    let calls = 0;
    const root = (await render({ shown: true, onRetry: () => calls++, retrying: false, error: "timeout" })).root;
    const retry = root.findByProps({ "aria-label": "Retry connection" });
    assert.strictEqual(retry.props.disabled, false);
    await act(async () => { retry.props.onClick(); });
    assert.strictEqual(calls, 1);

    const retrying = (await render({ shown: true, onRetry: () => {}, retrying: true })).root;
    assert.strictEqual(retrying.findByProps({ "aria-label": "Retry connection" }).props.disabled, true);
  });
});
