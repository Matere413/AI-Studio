// ─── Unit Tests: VerifyEmailPage ─────────────────────────────────
// Verifies the verify-email page reads BOTH `token` and `email` query
// params, POSTs `{email, token}` via `verifyEmail`, and renders the
// success / error UI. Uses the transpile + react-test-renderer harness
// shared with the auth-forms / auth-small-components tests (bare Node —
// no DOM, no Next server). `useSearchParams` and `verifyEmail` are
// mocked; `Suspense` is left as React's built-in (it renders its
// children directly when no promise is pending).

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

// Real AuthLayout — pass-through so the page renders its own content.
const authLayoutMod = loadComponent("src/features/auth/presentation/components/AuthLayout.tsx");
const authLayoutOverride = { AuthLayout: authLayoutMod.AuthLayout };

// Build a mock verifyEmail that records its args and resolves or rejects.
function buildVerifyMock(opts: { resolve?: boolean; rejectCode?: string } = {}) {
  const calls: Array<{ email: string; token: string }> = [];
  const verifyEmail = async (email: string, token: string) => {
    calls.push({ email, token });
    if (opts.rejectCode) {
      throw { code: opts.rejectCode, detail: "mock failure" };
    }
    return {
      id: "u1",
      email,
      email_verified: true,
      created_at: "2024-01-01T00:00:00Z",
    };
  };
  return { calls, verifyEmail };
}

// ─── VerifyEmailPage ────────────────────────────────────────────
void describe("VerifyEmailPage", () => {
  void it("reads token + email query params and POSTs {email, token} on success", async () => {
    const { calls, verifyEmail } = buildVerifyMock({ resolve: true });
    const useSearchParams = () => new URLSearchParams("token=abc&email=user%40example.com");
    const mod = loadComponent("src/app/auth/verify/page.tsx", {
      "@/features/auth/infrastructure/auth-api": { verifyEmail },
      "next/navigation": { useSearchParams },
      "@/features/auth/presentation/components/AuthLayout": authLayoutOverride,
    });
    const VerifyEmailPage = mod.default as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(VerifyEmailPage, null));
    });
    // Let the useEffect-driven verification resolve.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    // verifyEmail MUST be called with (email, token) in that order — the
    // backend requires BOTH in the body and the page reads them from the
    // query string (`?token=...&email=<urlencoded>`).
    assert.strictEqual(calls.length, 1, "verifyEmail MUST be called exactly once");
    assert.deepStrictEqual(calls[0], { email: "user@example.com", token: "abc" });

    // Success UI: the page shows "Email verified".
    const headings = renderer.root.findAllByType("h1").map((n) => n.children.join(""));
    assert.ok(
      headings.some((h) => /email verified/i.test(h)),
      "MUST render the success heading after a successful verification",
    );
  });

  void it("renders the error UI when verifyEmail rejects", async () => {
    const { calls, verifyEmail } = buildVerifyMock({ rejectCode: "token_expired" });
    const useSearchParams = () => new URLSearchParams("token=xyz&email=bad%40example.com");
    const mod = loadComponent("src/app/auth/verify/page.tsx", {
      "@/features/auth/infrastructure/auth-api": { verifyEmail },
      "next/navigation": { useSearchParams },
      "@/features/auth/presentation/components/AuthLayout": authLayoutOverride,
    });
    const VerifyEmailPage = mod.default as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(VerifyEmailPage, null));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    assert.strictEqual(calls.length, 1, "verifyEmail MUST still be attempted once");
    // Error UI: the page shows "Verification failed" + a role=alert message.
    const headings = renderer.root.findAllByType("h1").map((n) => n.children.join(""));
    assert.ok(
      headings.some((h) => /verification failed/i.test(h)),
      "MUST render the failure heading when verifyEmail rejects",
    );
    const alerts = renderer.root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error alert on verification failure");
    const alertText = alerts.map((a) => a.children.join("")).join(" ");
    // token_expired maps to the "expired" message.
    assert.ok(
      /expired/i.test(alertText),
      "MUST map token_expired to the expired-link message",
    );
  });

  void it("renders the error UI when token or email is missing from the query", async () => {
    const { calls, verifyEmail } = buildVerifyMock({ resolve: true });
    // No token param — only email.
    const useSearchParams = () => new URLSearchParams("email=user%40example.com");
    const mod = loadComponent("src/app/auth/verify/page.tsx", {
      "@/features/auth/infrastructure/auth-api": { verifyEmail },
      "next/navigation": { useSearchParams },
      "@/features/auth/presentation/components/AuthLayout": authLayoutOverride,
    });
    const VerifyEmailPage = mod.default as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(VerifyEmailPage, null));
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });

    // verifyEmail MUST NOT be called when a param is missing.
    assert.strictEqual(calls.length, 0, "verifyEmail MUST NOT be called when token is missing");
    const headings = renderer.root.findAllByType("h1").map((n) => n.children.join(""));
    assert.ok(
      headings.some((h) => /verification failed/i.test(h)),
      "MUST render the failure heading when a query param is missing",
    );
  });
});