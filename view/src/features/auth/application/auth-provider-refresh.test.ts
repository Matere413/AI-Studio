// ─── Unit Tests: AuthProvider refresh-failure redirect (slice 4 verify-fix) ──
// Proves at runtime that when a refresh-on-401 fails, the session-expired
// handler (registered by AuthProvider) sets window.location.href to
// "/login?next=<encoded-current-path>". This closes the gap left by the
// source-only inspection of handleSessionExpired.
//
// Two layers are exercised:
//   1. The pure redirect-URL builder (extracted so it is testable under
//      bare Node with no router/DOM).
//   2. The full chain: api-client fires the registered handler on
//      refresh failure → the handler sets window.location.href to the
//      expected /login?next=... URL.

import { describe, it, before, after, beforeEach } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

const require = createRequire(import.meta.url);

// ── Transpile + load helpers (mirror auth-provider.test.ts harness) ──
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

// ── Mock auth-api (provider only needs the shape; getCurrentUser rejects ──
// so bootstrap lands on the anonymous path quickly).
interface MockApi {
  getCurrentUser: () => Promise<unknown>;
  loginUser: () => Promise<unknown>;
  registerUser: () => Promise<unknown>;
  logoutUser: () => Promise<void>;
  logoutAllUser: () => Promise<void>;
  resendVerification: () => Promise<void>;
}

function buildMockApi(): MockApi {
  return {
    getCurrentUser: async () => {
      throw { code: "unauthenticated", detail: "no token" };
    },
    loginUser: async () => ({ id: "u1", email: "a@b.com", email_verified: true, created_at: "t" }),
    registerUser: async () => ({ id: "u2", email: "a@b.com", email_verified: false, created_at: "t" }),
    logoutUser: async () => undefined,
    logoutAllUser: async () => undefined,
    resendVerification: async () => undefined,
  };
}

// ── Mock window.location so the redirect is observable under bare Node ──
function makeMockWindow(initialPath: string) {
  let hrefValue = initialPath;
  const location = {
    pathname: "/studio",
    search: "",
    get href() {
      return hrefValue;
    },
    set href(value: string) {
      hrefValue = value;
    },
  };
  return { window: { location }, getHref: () => hrefValue };
}

before(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://test-api.example.com";
});

after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete (globalThis as Record<string, unknown>).window;
});

async function loadProviderModules(mockApi: MockApi) {
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
  const userMod = loadModule(userJs, {});
  const reducerMod = loadModule(reducerJs, {
    "../domain/user.ts": userMod.exports,
  });
  const contextMod = loadModule(contextJs, {});
  const useAuthMod = loadModule(useAuthJs, {
    "./auth-context.ts": contextMod.exports,
    "../domain/user.ts": userMod.exports,
  });
  const providerMod = loadModule(providerJs, {
    "./auth-reducer.ts": reducerMod.exports,
    "./auth-context.ts": contextMod.exports,
    "./use-auth.ts": useAuthMod.exports,
    "../domain/user.ts": userMod.exports,
    "../infrastructure/auth-api.ts": mockApi,
  });
  return {
    AuthProvider: providerMod.exports.AuthProvider as React.ComponentType<{ children: React.ReactNode }>,
    buildLoginRedirectUrl: providerMod.exports.buildLoginRedirectUrl as (
      currentPath: string,
    ) => string,
    useAuth: useAuthMod.exports.useAuth as () => Record<string, unknown>,
  };
}

void describe("AuthProvider refresh-failure redirect (slice 4 verify-fix)", () => {
  void it("buildLoginRedirectUrl encodes the current path into the next param", () => {
    // Pure function — no window, no DOM. Proves the URL shape.
    const { buildLoginRedirectUrl } = await_loadProviderModulesSync();
    assert.strictEqual(
      buildLoginRedirectUrl("/studio"),
      "/login?next=%2Fstudio",
    );
    // Path + query string preserved and encoded.
    assert.strictEqual(
      buildLoginRedirectUrl("/projects?owner=me"),
      "/login?next=%2Fprojects%3Fowner%3Dme",
    );
  });

  void it("handleSessionExpired sets window.location.href to /login?next=<current-path> at runtime", async () => {
    const mockApi = buildMockApi();
    const { AuthProvider, useAuth } = await loadProviderModules(mockApi);
    const mock = makeMockWindow("http://localhost/studio");
    (globalThis as Record<string, unknown>).window = mock.window;

    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = () => {
      captured.current = useAuth();
      return null;
    };

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    // The provider exposes handleSessionExpired; calling it MUST redirect.
    const handleSessionExpired = captured.current!.handleSessionExpired as () => void;
    assert.strictEqual(typeof handleSessionExpired, "function");
    handleSessionExpired();

    // window.location.href MUST now be /login?next=<encoded current path>.
    // The provider reads window.location.pathname + search at call time.
    assert.strictEqual(
      mock.getHref(),
      "/login?next=%2Fstudio",
      "handleSessionExpired MUST set window.location.href to /login?next=<encoded path>",
    );

    TestRenderer.act(() => {
      renderer.unmount();
    });
  });

  void it("end-to-end: api-client refresh failure fires the registered handler which redirects to /login", async () => {
    // Wire the real AuthProvider's handleSessionExpired into the real
    // api-client's setSessionExpiredHandler, then trigger a refresh
    // failure and assert the redirect happens.
    const mockApi = buildMockApi();
    const { AuthProvider, useAuth } = await loadProviderModules(mockApi);
    const mock = makeMockWindow("http://localhost/studio/projects");
    // pathname reflects the current route so the handler reads it.
    mock.window.location.pathname = "/studio/projects";
    (globalThis as Record<string, unknown>).window = mock.window;

    // Mount the provider so it registers the handler.
    const captured: { current: Record<string, unknown> | null } = { current: null };
    const Consumer = () => {
      captured.current = useAuth();
      return null;
    };
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(
        React.createElement(AuthProvider, null, React.createElement(Consumer, null)),
      );
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    // Now drive the api-client directly with a refresh failure.
    const apiUrl = "http://test-api.example.com/projects";
    const refreshUrl = "http://test-api.example.com/auth/refresh";
    const calls: { url: string }[] = [];
    globalThis.fetch = (async (input: URL | RequestInfo) => {
      const url = input.toString();
      calls.push({ url });
      if (url === refreshUrl) {
        return new Response(JSON.stringify({ error: { code: "invalid_refresh_token" } }), {
          status: 401,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ error: { code: "unauthenticated" } }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }) as typeof globalThis.fetch;

    const { fetchWithSession } = await import("../../../shared/infrastructure/api-client.ts");
    await fetchWithSession(apiUrl).catch(() => {});

    // The registered handler MUST have fired and set window.location.href.
    assert.strictEqual(
      mock.getHref(),
      "/login?next=%2Fstudio%2Fprojects",
      "refresh failure MUST trigger the AuthProvider handler which redirects to /login?next=<path>",
    );

    TestRenderer.act(() => {
      renderer.unmount();
    });
  });
});

// Helper to synchronously load provider modules for the pure-function test.
// `await` is not allowed at the top of an it() block, so this is a small
// adapter that re-loads via the same harness used above.
function await_loadProviderModulesSync() {
  // Reuse the same transpile/load path; the pure test does not need React.
  const mockApi = buildMockApi();
  const mod = loadProviderModulesPure(mockApi);
  return { buildLoginRedirectUrl: mod.buildLoginRedirectUrl };
}

function loadProviderModulesPure(mockApi: MockApi) {
  const providerJs = transpileModule(
    join(process.cwd(), "src/features/auth/application/auth-provider.tsx"),
  );
  // Minimal deps — only buildLoginRedirectUrl is used, which has no deps.
  const providerMod = loadModule(providerJs, {
    "../infrastructure/auth-api.ts": mockApi,
  });
  return {
    buildLoginRedirectUrl: providerMod.exports.buildLoginRedirectUrl as (
      currentPath: string,
    ) => string,
  };
}