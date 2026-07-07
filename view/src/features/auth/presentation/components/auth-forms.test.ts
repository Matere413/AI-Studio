// ─── Unit Tests: LoginForm + RegisterForm ───────────────────────
// Verifies client-side validation, submit flow, backend error-code
// mapping (weak_password, email_taken, invalid_credentials), and the
// redirect to `next` or `/` on success.

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

// ── Mock useAuth + next/navigation + AuthLayout ─────────────────
function buildUseAuthMock(overrides: Record<string, unknown> = {}) {
  return {
    login: async (_e: string, _p: string) => true,
    register: async (_e: string, _p: string) => true,
    isAuthenticated: false,
    isVerified: false,
    user: null,
    status: "unauthenticated",
    isBootstrapping: false,
    error: null,
    logout: async () => undefined,
    logoutGlobal: async () => undefined,
    resendVerification: async () => true,
    ...overrides,
  };
}

function buildRouterMock(next?: string | null) {
  const pushed: string[] = [];
  // Default preserves the historical `next=/projects` contract; pass
  // null explicitly to simulate the absence of a next param.
  const nextValue = next === undefined ? "/projects" : next;
  const search = nextValue === null ? "" : `next=${encodeURIComponent(nextValue)}`;
  return {
    pushed,
    router: {
      push: (url: string) => { pushed.push(url); },
      replace: (url: string) => { pushed.push(url); },
    },
    useSearchParams: () => new URLSearchParams(search),
  };
}

// Real AuthLayout — pass-through so the forms render their content.
const authLayoutMod = loadComponent("src/features/auth/presentation/components/AuthLayout.tsx");
const authLayoutOverride = { AuthLayout: authLayoutMod.AuthLayout };

// Real sanitizeNext — transpiled from the util so the forms' open-
// redirect guard runs under test (spec: LoginForm/RegisterForm honor
// a safe `next`, fall back to /studio).
const sanitizeNextMod = loadComponent("src/features/auth/presentation/utils/sanitize-next.ts");
const sanitizeNextOverride = { sanitizeNext: sanitizeNextMod.sanitizeNext };

// Find the <form> in a rendered tree and invoke its onSubmit with a fake event.
function submitForm(root: TestRenderer.ReactTestInstance): Promise<void> {
  const form = root.findByType("form");
  const ev = { preventDefault: () => undefined };
  return act(async () => form.props.onSubmit(ev));
}

// ─── LoginForm ─────────────────────────────────────────────────
void describe("LoginForm", () => {
  void it("shows a client-side error when email is empty on submit", async () => {
    const authMock = buildUseAuthMock({ login: async () => true });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/LoginForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const LoginForm = mod.LoginForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LoginForm, null));
    });
    const root = renderer.root;
    await submitForm(root);
    // An error alert must be visible.
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show a validation error when email is empty");
  });

  void it("calls login(email, password) and redirects to next on success", async () => {
    let loginArgs: string[] = [];
    const authMock = buildUseAuthMock({
      login: async (e: string, p: string) => { loginArgs = [e, p]; return true; },
    });
    const { router, useSearchParams, pushed } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/LoginForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const LoginForm = mod.LoginForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LoginForm, null));
    });
    const root = renderer.root;
    const email = root.findByProps({ "aria-label": "Email" });
    const password = root.findByProps({ "aria-label": "Password" });
    await act(async () => email.props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => password.props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);

    assert.deepStrictEqual(loginArgs, ["a@b.com", "StrongPass1!"]);
    assert.ok(pushed.some((u) => u === "/projects" || u.startsWith("/projects")), "MUST redirect to next=/projects");
  });

  void it("falls back to /studio when no next param is present", async () => {
    const authMock = buildUseAuthMock({ login: async () => true });
    const { router, useSearchParams, pushed } = buildRouterMock(null);
    const mod = loadComponent("src/features/auth/presentation/components/LoginForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const LoginForm = mod.LoginForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LoginForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    assert.ok(
      pushed.some((u) => u === "/studio"),
      `MUST fall back to /studio when next is absent; got: ${JSON.stringify(pushed)}`,
    );
  });

  void it("maps a 401 invalid_credentials to an inline error message", async () => {
    const authMock = buildUseAuthMock({
      login: async () => false,
      error: "invalid_credentials",
    });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/LoginForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const LoginForm = mod.LoginForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LoginForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "wrong" } }));
    await submitForm(root);
    // The error alert must mention the credentials problem.
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error after failed login");
    const text = alerts.map((a) => a.children.join("")).join(" ");
    assert.ok(/invalid|credentials|email or password/i.test(text), "Error MUST map invalid_credentials to a user message");
  });

  // 4R WARNING 4 — rate_limited (429) MUST surface a "too many attempts"
  // message, not the generic fallback, so the user knows to wait.
  void it("maps a 429 rate_limited to a too-many-attempts message", async () => {
    const authMock = buildUseAuthMock({
      login: async () => false,
      error: "rate_limited",
    });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/LoginForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const LoginForm = mod.LoginForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LoginForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error for rate_limited");
    const text = alerts.map((a) => a.children.join("")).join(" ");
    assert.ok(
      /too many attempts|try again shortly/i.test(text),
      "MUST map rate_limited to a 'too many attempts' message, not the generic fallback",
    );
  });
});

// ─── RegisterForm ──────────────────────────────────────────────
void describe("RegisterForm", () => {
  void it("shows a client-side error when password is too short", async () => {
    const authMock = buildUseAuthMock({ register: async () => true });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "short1" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show a validation error for a short password");
  });

  void it("shows a client-side error when confirm password does not match", async () => {
    const authMock = buildUseAuthMock({ register: async () => true });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "Different1!" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show a mismatch error");
  });

  void it("calls register(email, password) and redirects to /studio on success", async () => {
    let registerArgs: string[] = [];
    const authMock = buildUseAuthMock({
      register: async (e: string, p: string) => { registerArgs = [e, p]; return true; },
    });
    const { router, useSearchParams, pushed } = buildRouterMock(null);
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    assert.deepStrictEqual(registerArgs, ["a@b.com", "StrongPass1!"]);
    // Spec: no onboarding screen — the user MUST be redirected to /studio.
    assert.ok(
      pushed.some((u) => u === "/studio"),
      `MUST redirect to /studio after register (no onboarding); got: ${JSON.stringify(pushed)}`,
    );
  });

  void it("redirects to the safe next param on success", async () => {
    const authMock = buildUseAuthMock({ register: async () => true });
    const { router, useSearchParams, pushed } = buildRouterMock("/studio?foo=1");
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    assert.ok(
      pushed.some((u) => u === "/studio?foo=1"),
      `MUST honor a safe next=/studio?foo=1; got: ${JSON.stringify(pushed)}`,
    );
  });

  void it("falls back to /studio on success when no next param is present", async () => {
    const authMock = buildUseAuthMock({ register: async () => true });
    const { router, useSearchParams, pushed } = buildRouterMock(null);
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    assert.ok(
      pushed.some((u) => u === "/studio"),
      `MUST fall back to /studio when next is absent; got: ${JSON.stringify(pushed)}`,
    );
  });

  void it("maps a 409 email_taken to 'Email already registered'", async () => {
    const authMock = buildUseAuthMock({
      register: async () => false,
      error: "email_taken",
    });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "taken@e.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error");
    const text = alerts.map((a) => a.children.join("")).join(" ");
    assert.ok(/already registered/i.test(text), "MUST map email_taken to 'Email already registered'");
  });

  void it("maps a 400 weak_password to the strength requirement message", async () => {
    // The backend can reject a password that passes the client-side strength
    // check but is still too weak server-side (e.g. a reused / breached
    // password). The form MUST surface the backend's weak_password code as a
    // readable strength message rather than the generic fallback.
    const authMock = buildUseAuthMock({
      register: async () => false,
      error: "weak_password",
    });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "weak@e.com" } }));
    // Password passes the client-side check (12+ chars, letter, digit) so the
    // local validation does NOT short-circuit — the error must come from the
    // backend weak_password mapping.
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error for a backend weak_password rejection");
    const text = alerts.map((a) => a.children.join("")).join(" ");
    assert.ok(
      /at least 12 characters|letter and a digit/i.test(text),
      "MUST map weak_password to the strength requirement message, not the generic fallback",
    );
  });

  // 4R WARNING 4 — rate_limited (429) MUST surface a "too many attempts"
  // message on the register form too.
  void it("maps a 429 rate_limited to a too-many-attempts message", async () => {
    const authMock = buildUseAuthMock({
      register: async () => false,
      error: "rate_limited",
    });
    const { router, useSearchParams } = buildRouterMock();
    const mod = loadComponent("src/features/auth/presentation/components/RegisterForm.tsx", {
      "@/features/auth/application/use-auth": { useAuth: () => authMock },
      "next/navigation": { useRouter: () => router, useSearchParams },
      "./AuthLayout": authLayoutOverride,
      "@/features/auth/presentation/utils/sanitize-next": sanitizeNextOverride,
    });
    const RegisterForm = mod.RegisterForm as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(RegisterForm, null));
    });
    const root = renderer.root;
    await act(async () => root.findByProps({ "aria-label": "Email" }).props.onChange({ target: { value: "a@b.com" } }));
    await act(async () => root.findByProps({ "aria-label": "Password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await act(async () => root.findByProps({ "aria-label": "Confirm password" }).props.onChange({ target: { value: "StrongPass1!" } }));
    await submitForm(root);
    const alerts = root.findAllByProps({ role: "alert" });
    assert.ok(alerts.length > 0, "MUST show an error for rate_limited");
    const text = alerts.map((a) => a.children.join("")).join(" ");
    assert.ok(
      /too many attempts|try again shortly/i.test(text),
      "MUST map rate_limited to a 'too many attempts' message on the register form too",
    );
  });
});