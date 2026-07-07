// ─── Unit Tests: AuthProvider + useAuth ──────────────────────────
// Verifies the AuthProvider bootstraps via GET /auth/me on mount,
// exposes the documented context shape, and that logoutGlobal
// calls the /auth/logout-all wrapper (the hyphenated endpoint name).

import { describe, it, before, after } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

const require = createRequire(import.meta.url);

// ── Transpile + load helpers (mirror the ChatPanel test harness) ──
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

// ── Mock auth-api ───────────────────────────────────────────────
// The provider imports these from ../infrastructure/auth-api. We
// override that relative path so the provider runs in isolation.
interface MockApi {
  getCurrentUser: () => Promise<unknown>;
  loginUser: (email: string, password: string) => Promise<unknown>;
  registerUser: (email: string, password: string) => Promise<unknown>;
  logoutUser: () => Promise<void>;
  logoutAllUser: () => Promise<void>;
  refreshTokens: () => Promise<unknown>;
  resendVerification: () => Promise<void>;
  verifyEmail: (email: string, token: string) => Promise<unknown>;
}

function buildMockApi(overrides: Partial<MockApi> = {}): MockApi & { calls: string[] } {
  const calls: string[] = [];
  const api: MockApi & { calls: string[] } = {
    calls,
    getCurrentUser: async () => {
      calls.push("me");
      return { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
    },
    loginUser: async (_e: string, _p: string) => {
      calls.push("login");
      return { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
    },
    registerUser: async (_e: string, _p: string) => {
      calls.push("register");
      return { id: "u2", email: "a@b.com", email_verified: false, created_at: "t" };
    },
    logoutUser: async () => {
      calls.push("logout");
    },
    logoutAllUser: async () => {
      calls.push("logout-all");
    },
    refreshTokens: async () => {
      calls.push("refresh");
      return { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
    },
    resendVerification: async () => {
      calls.push("resend");
    },
    verifyEmail: async (_e: string, _t: string) => {
      calls.push("verify");
      return { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
    },
    ...overrides,
  };
  return api;
}

async function loadProvider(mockApi: MockApi) {
  const providerJs = transpileModule(
    join(process.cwd(), "src/features/auth/application/auth-provider.tsx"),
  );
  const useAuthJs = transpileModule(
    join(process.cwd(), "src/features/auth/application/use-auth.ts"),
  );
  const contextJs = transpileModule(
    join(process.cwd(), "src/features/auth/application/auth-context.ts"),
  );
  const reducerJs = transpileModule(
    join(process.cwd(), "src/features/auth/application/auth-reducer.ts"),
  );
  const userJs = transpileModule(
    join(process.cwd(), "src/features/auth/domain/user.ts"),
  );
  // Load domain + reducer first (no external deps).
  const userMod = loadModule(userJs, {});
  const reducerMod = loadModule(reducerJs, {
    "../domain/user.ts": userMod.exports,
  });
  // use-auth needs the context type (type-only, erased by transpile) +
  // the AuthContext runtime value.
  const contextMod = loadModule(contextJs, {});
  // Load use-auth with the context module.
  const useAuthMod = loadModule(useAuthJs, {
    "./auth-context.ts": contextMod.exports,
    "../domain/user.ts": userMod.exports,
  });
  // Load provider with reducer, context, use-auth type, and mocked auth-api.
  const providerMod = loadModule(providerJs, {
    "./auth-reducer.ts": reducerMod.exports,
    "./auth-context.ts": contextMod.exports,
    "./use-auth.ts": useAuthMod.exports,
    "../domain/user.ts": userMod.exports,
    "../infrastructure/auth-api.ts": mockApi,
  });
  return {
    AuthProvider: providerMod.exports.AuthProvider as React.ComponentType<{ children: React.ReactNode }>,
    useAuth: useAuthMod.exports.useAuth as () => Record<string, unknown>,
  };
}

// ── A consumer component that reads useAuth and exposes it via a ref ──
function makeConsumer(captured: { current: Record<string, unknown> | null }, useAuth: () => Record<string, unknown>) {
  return function Consumer() {
    captured.current = useAuth();
    return null;
  };
}

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
});

void describe("AuthProvider + useAuth", () => {
  void it("calls getCurrentUser on mount to bootstrap (authenticated path)", async () => {
    const mockApi = buildMockApi();
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    // Allow the bootstrap effect (getCurrentUser) to flush.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    assert.ok(mockApi.calls.includes("me"), "getCurrentUser MUST be called on mount");
    const ctx = captured.current!;
    assert.strictEqual(ctx.status, "authenticated");
    assert.strictEqual((ctx.user as { id: string }).id, "u1");
    assert.strictEqual(ctx.isAuthenticated, true);
    assert.strictEqual(ctx.isVerified, true);
    assert.strictEqual(ctx.isBootstrapping, false);
  });

  void it("stays anonymous (no error UI) when getCurrentUser rejects (no cookie)", async () => {
    const mockApi = buildMockApi({
      getCurrentUser: async () => {
        throw { code: "unauthenticated", detail: "no token" };
      },
    });
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const ctx = captured.current!;
    assert.strictEqual(ctx.status, "unauthenticated");
    assert.strictEqual(ctx.user, null);
    assert.strictEqual(ctx.isAuthenticated, false);
    assert.strictEqual(ctx.isBootstrapping, false);
    assert.strictEqual(ctx.error, null, "bootstrap failure MUST NOT surface an error UI");
  });

  void it("exposes login that calls loginUser and flips to authenticated", async () => {
    const mockApi = buildMockApi({
      getCurrentUser: async () => {
        throw { code: "unauthenticated", detail: "no token" };
      },
    });
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const login = captured.current!.login as (email: string, password: string) => Promise<boolean>;
    let result = false;
    await act(async () => {
      result = await login("a@b.com", "StrongPass1!");
    });

    assert.ok(mockApi.calls.includes("login"));
    assert.strictEqual(result, true);
    assert.strictEqual(captured.current!.status, "authenticated");
    assert.strictEqual(captured.current!.isAuthenticated, true);
  });

  void it("exposes logoutGlobal that calls /auth/logout-all", async () => {
    const mockApi = buildMockApi();
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const logoutGlobal = captured.current!.logoutGlobal as () => Promise<void>;
    await act(async () => {
      await logoutGlobal();
    });

    assert.ok(mockApi.calls.includes("logout-all"), "logoutGlobal MUST call /auth/logout-all");
    assert.strictEqual(captured.current!.status, "unauthenticated");
    assert.strictEqual(captured.current!.user, null);
  });

  void it("exposes resendVerification that calls /auth/resend-verification", async () => {
    const mockApi = buildMockApi();
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const resend = captured.current!.resendVerification as () => Promise<boolean>;
    let ok = false;
    await act(async () => {
      ok = await resend();
    });
    assert.ok(mockApi.calls.includes("resend"));
    assert.strictEqual(ok, true);
  });

  void it("exposes register that calls registerUser", async () => {
    const mockApi = buildMockApi({
      getCurrentUser: async () => {
        throw { code: "unauthenticated", detail: "no token" };
      },
    });
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    const register = captured.current!.register as (email: string, password: string) => Promise<boolean>;
    let result = false;
    await act(async () => {
      result = await register("a@b.com", "StrongPass1!");
    });
    assert.ok(mockApi.calls.includes("register"));
    assert.strictEqual(result, true);
  });

  // 4R CRITICAL 2 — verifyEmail action updates the auth context with the
  // verified user returned by POST /auth/verify-email.
  void it("exposes verifyEmail that calls the API and updates the user to verified", async () => {
    const mockApi = buildMockApi({
      getCurrentUser: async () => {
        // Start as an unverified authenticated user (the common case when
        // someone clicks a verification link while logged in).
        return { id: "u1", email: "a@b.com", email_verified: false, created_at: "t" };
      },
      verifyEmail: async (_e: string, _t: string) => {
        mockApi.calls.push("verify");
        return { id: "u1", email: "a@b.com", email_verified: true, created_at: "t" };
      },
    });
    const { AuthProvider, useAuth } = await loadProvider(mockApi);
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = makeConsumer(captured, useAuth);

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    // Precondition: the user is authenticated but unverified.
    assert.strictEqual(captured.current!.isAuthenticated, true);
    assert.strictEqual(captured.current!.isVerified, false);

    const verifyEmail = captured.current!.verifyEmail as (email: string, token: string) => Promise<boolean>;
    let result = false;
    await act(async () => {
      result = await verifyEmail("a@b.com", "tok-123");
    });

    assert.ok(mockApi.calls.includes("verify"), "verifyEmail MUST call the /auth/verify-email API");
    assert.strictEqual(result, true, "verifyEmail MUST return true on success");
    // CRITICAL 2: the auth context MUST be updated with the verified user.
    assert.strictEqual(captured.current!.isVerified, true, "the user MUST be marked verified in the context");
    assert.strictEqual((captured.current!.user as { email_verified: boolean }).email_verified, true);
  });
});