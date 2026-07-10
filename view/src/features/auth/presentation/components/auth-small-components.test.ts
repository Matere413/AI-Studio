// ─── Unit Tests: AuthLayout, EmailVerificationBanner ──────────
// Note: LogoutButton was removed when the studio top bar Publish control
// absorbed the logout affordance (change: add-landing-auth).
// Verifies the small auth presentation components render the right
// children / fire the right callbacks. Uses the transpile+react-test-renderer
// harness shared with the ChatPanel test.

import { describe, it, before, after } from "node:test";
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

function loadComponent(file: string, requireOverrides: Record<string, unknown> = {}) {
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

// ─── AuthLayout ─────────────────────────────────────────────────
void describe("AuthLayout", () => {
  void it("renders its children inside a centered dark panel", async () => {
    const mod = loadComponent("src/features/auth/presentation/components/AuthLayout.tsx");
    const AuthLayout = mod.AuthLayout as React.ComponentType<{ children: React.ReactNode }>;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthLayout, null, React.createElement("div", { id: "child" }, "Hello")),
      );
    });
    const root = renderer.root;
    // Child content is rendered.
    const child = root.findByProps({ id: "child" });
    assert.ok(child, "MUST render the provided children");
    assert.strictEqual(child.children[0], "Hello");
  });
});

// ─── EmailVerificationBanner ────────────────────────────────────
void describe("EmailVerificationBanner", () => {
  void it("renders when shown=true with a resend control", async () => {
    const mod = loadComponent("src/features/auth/presentation/components/EmailVerificationBanner.tsx");
    const Banner = mod.EmailVerificationBanner as React.ComponentType<{
      shown: boolean;
      onResend: () => void;
      resending?: boolean;
    }>;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(Banner, { shown: true, onResend: () => undefined }),
      );
    });
    const root = renderer.root;
    // The banner has role="alert" (semantic, survives styling refactors).
    const alert = root.findByProps({ role: "alert" });
    assert.ok(alert, "MUST render a role=alert region when shown");
    // A resend button must be present.
    const resend = root.findByProps({ "aria-label": "Resend verification email" });
    assert.ok(resend, "MUST include a resend control");
  });

  void it("renders nothing when shown=false", async () => {
    const mod = loadComponent("src/features/auth/presentation/components/EmailVerificationBanner.tsx");
    const Banner = mod.EmailVerificationBanner as React.ComponentType<{
      shown: boolean;
      onResend: () => void;
    }>;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(Banner, { shown: false, onResend: () => undefined }),
      );
    });
    // No role=alert region when hidden.
    const alerts = renderer.root.findAllByProps({ role: "alert" });
    assert.strictEqual(alerts.length, 0, "MUST NOT render the banner when shown=false");
  });

  void it("calls onResend when the resend control is activated", async () => {
    const mod = loadComponent("src/features/auth/presentation/components/EmailVerificationBanner.tsx");
    const Banner = mod.EmailVerificationBanner as React.ComponentType<{
      shown: boolean;
      onResend: () => void;
    }>;
    let resendCount = 0;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(Banner, { shown: true, onResend: () => { resendCount++; } }),
      );
    });
    const resend = renderer.root.findByProps({ "aria-label": "Resend verification email" });
    await act(async () => resend.props.onClick());
    assert.strictEqual(resendCount, 1, "onResend MUST fire");
  });
});