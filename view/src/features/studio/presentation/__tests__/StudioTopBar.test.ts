// ─── Unit Tests: StudioTopBar ──────────────────────────────────
// Verifies the studio top bar Publish/Log-out session-control contract.

import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

const require = createRequire(import.meta.url);

function loadTopBar(requireOverrides: Record<string, unknown>) {
  const source = readFileSync(
    join(process.cwd(), "src/features/studio/presentation/components/StudioTopBar.tsx"),
    "utf8",
  );
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
  }).outputText;
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

function LinkMock({
  href,
  children,
  ...props
}: {
  href: unknown;
  children: React.ReactNode;
  [key: string]: unknown;
}) {
  return React.createElement("a", { href: String(href), ...props }, children);
}

function BannerStub({ shown }: { shown: boolean }) {
  return shown ? React.createElement("div", { "data-testid": "banner" }) : null;
}

function RetryBannerStub({ shown, onRetry, retrying }: { shown: boolean; onRetry: () => void; retrying?: boolean }) {
  return shown ? React.createElement("button", { "data-testid": "bootstrap-retry-banner", onClick: onRetry, disabled: retrying }) : null;
}

interface MockAuthValue {
  isAuthenticated: boolean;
  logout: () => Promise<void>;
  isVerified: boolean;
  isBootstrapping: boolean;
  resendVerification: () => Promise<boolean>;
  isBootstrapRetryable: boolean;
  isRetryingBootstrap: boolean;
  bootstrapError: string | null;
  retryBootstrap: () => void;
}

function buildMockAuth(overrides: Partial<MockAuthValue> = {}) {
  const calls: string[] = [];
  return {
    calls,
    isAuthenticated: true,
    isVerified: true,
    isBootstrapping: false,
    logout: async () => {
      calls.push("logout");
    },
    resendVerification: async () => true,
    isBootstrapRetryable: false,
    isRetryingBootstrap: false,
    bootstrapError: null,
    retryBootstrap: () => { calls.push("retry"); },
    ...overrides,
  };
}

function buildOverrides(mockAuth: MockAuthValue) {
  return {
    "@/features/auth/application/use-auth": { useAuth: () => mockAuth },
    "@/features/auth/presentation/components/EmailVerificationBanner": {
      EmailVerificationBanner: BannerStub,
    },
    "@/features/auth/presentation/components/BootstrapRetryBanner": { BootstrapRetryBanner: RetryBannerStub },
    "next/link": LinkMock,
  };
}

function collectText(node: TestRenderer.ReactTestInstance, acc: string[] = []): string[] {
  for (const child of node.children ?? []) {
    if (typeof child === "string") acc.push(child);
    else if (typeof child === "number") acc.push(String(child));
    else if (typeof child === "object" && child !== null) {
      collectText(child as TestRenderer.ReactTestInstance, acc);
    }
  }
  return acc;
}

void describe("StudioTopBar", () => {
  void it("authenticated state renders a single Log out button that calls useAuth().logout", async () => {
    const mockAuth = buildMockAuth();
    const mod = loadTopBar(buildOverrides(mockAuth));
    const StudioTopBar = mod.StudioTopBar as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(StudioTopBar, null));
    });

    const control = renderer.root.findAllByProps({ "aria-label": "Log out" });
    assert.strictEqual(control.length, 1, "MUST render exactly one Log out control");
    assert.strictEqual(control[0].props["data-state"], "authenticated");
    await act(async () => {
      await control[0].props.onClick();
    });
    assert.deepStrictEqual(mockAuth.calls, ["logout"]);
  });

  void it("anonymous state renders a Sign in link to /login and never calls logout", async () => {
    const mockAuth = buildMockAuth({ isAuthenticated: false, isVerified: false });
    const mod = loadTopBar(buildOverrides(mockAuth));
    const StudioTopBar = mod.StudioTopBar as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(StudioTopBar, null));
    });

    const anchors = renderer.root.findAllByType("a").filter((anchor) => anchor.props.href === "/login");
    assert.strictEqual(anchors.length, 1, "MUST render exactly one /login anchor");
    assert.strictEqual(anchors[0].props["data-state"], "anonymous");
    assert.ok(collectText(anchors[0]).join(" ").includes("Sign in"));
    assert.deepStrictEqual(mockAuth.calls, [], "logout MUST NOT be called anonymously");
  });

  void it("renders exactly one session control in each auth state", async () => {
    for (const mockAuth of [
      buildMockAuth(),
      buildMockAuth({ isAuthenticated: false, isVerified: false }),
    ]) {
      const mod = loadTopBar(buildOverrides(mockAuth));
      const StudioTopBar = mod.StudioTopBar as React.ComponentType;
      let renderer!: TestRenderer.ReactTestRenderer;
      await act(async () => {
        renderer = TestRenderer.create(React.createElement(StudioTopBar, null));
      });
      const sessionControls = [
        ...renderer.root.findAllByType("button").filter((button) =>
          button.props["data-state"] === "authenticated" || button.props["data-state"] === "anonymous",
        ),
        ...renderer.root.findAllByType("a").filter((anchor) =>
          anchor.props["data-state"] === "authenticated" || anchor.props["data-state"] === "anonymous",
        ),
      ];
      assert.strictEqual(sessionControls.length, 1, "MUST have one stable session-control slot");
    }
  });
  void it("shows recovery instead of a false anonymous sign-in", async () => {
    const auth = buildMockAuth({ isAuthenticated: false, isVerified: false, isBootstrapRetryable: true });
    const StudioTopBar = loadTopBar(buildOverrides(auth)).StudioTopBar as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => { renderer = TestRenderer.create(React.createElement(StudioTopBar, null)); });
    assert.strictEqual(renderer.root.findAllByProps({ "data-testid": "bootstrap-retry-banner" }).length, 1);
    assert.strictEqual(renderer.root.findAllByType("a").filter((anchor) => anchor.props.href === "/login").length, 0);
    const bootstrapping = buildMockAuth({ isAuthenticated: false, isVerified: false, isBootstrapping: true });
    const BootstrappingTopBar = loadTopBar(buildOverrides(bootstrapping)).StudioTopBar as React.ComponentType;
    await act(async () => { renderer = TestRenderer.create(React.createElement(BootstrappingTopBar, null)); });
    assert.strictEqual(renderer.root.findAllByType("a").filter((anchor) => anchor.props.href === "/login").length, 0);
  });

  void it("wires retryBootstrap and disables it while retrying", async () => {
    const auth = buildMockAuth({ isAuthenticated: false, isVerified: false, isBootstrapRetryable: true });
    const StudioTopBar = loadTopBar(buildOverrides(auth)).StudioTopBar as React.ComponentType;
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => { renderer = TestRenderer.create(React.createElement(StudioTopBar, null)); });
    const retry = renderer.root.findByProps({ "data-testid": "bootstrap-retry-banner" });
    assert.strictEqual(retry.props.disabled, false);
    await act(async () => { retry.props.onClick(); });
    assert.deepStrictEqual(auth.calls, ["retry"]);
    const retrying = buildMockAuth({ isAuthenticated: false, isVerified: false, isBootstrapRetryable: true, isRetryingBootstrap: true });
    const RetryingTopBar = loadTopBar(buildOverrides(retrying)).StudioTopBar as React.ComponentType;
    await act(async () => { renderer = TestRenderer.create(React.createElement(RetryingTopBar, null)); });
    assert.strictEqual(renderer.root.findByProps({ "data-testid": "bootstrap-retry-banner" }).props.disabled, true);
  });

});
