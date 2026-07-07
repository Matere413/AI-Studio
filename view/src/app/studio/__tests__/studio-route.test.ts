// ─── Unit Tests (behavior): Studio route relocation ──────────────
// Verifies the `/studio` route mounts the expected Studio shell after the
// route split. The page is a client component; this harness transpiles it and
// mocks the client hooks (`useAuth`, `useGenerationJob`) plus the four
// presentational components (ChatPanel, StudioTopBar, StudioCanvas,
// AssetsDrawer) so the tree renders without a browser.
//
// Asserts the rendered tree contains the stable Studio shell markers
// (ChatPanel + StudioTopBar + StudioCanvas + AssetsDrawer). Requiring all four
// markers catches blank or partially wired route output without claiming full
// browser/runtime coverage.

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
  // The Studio page's responsive-drawer effect reads `window.innerWidth`
  // and registers a resize listener. react-test-renderer runs in Node,
  // so we provide a minimal window stub.
  if (typeof globalThis.window === "undefined") {
    const listeners: Array<() => void> = [];
    (globalThis as { window: unknown }).window = {
      innerWidth: 1280,
      addEventListener: (_event: string, fn: () => void) => { listeners.push(fn); },
      removeEventListener: (_event: string, fn: () => void) => {
        const i = listeners.indexOf(fn);
        if (i >= 0) listeners.splice(i, 1);
      },
    };
  }
});
after(() => {
  delete process.env.NEXT_PUBLIC_API_BASE_URL;
});

// ── Mocks for the four Studio shell components ──────────────────
// Each renders a marker node so the tree is assertable.
const ChatPanelMock = () => React.createElement("div", { "data-mock": "ChatPanel" });
const StudioTopBarMock = () => React.createElement("div", { "data-mock": "StudioTopBar" });
const StudioCanvasMock = () => React.createElement("div", { "data-mock": "StudioCanvas" });
const AssetsDrawerMock = () => React.createElement("div", { "data-mock": "AssetsDrawer" });

// Mock useGenerationJob — returns a stable idle state so the page
// effects don't try to open a real WebSocket.
const useGenerationJobMock = () => ({
  events: [],
  state: "idle" as const,
  progress: null,
  retry: 0,
});

// Mock useAuth — unauthenticated so no project-save path triggers.
const useAuthMock = () => ({
  isAuthenticated: false,
  isVerified: false,
  user: null,
  status: "unauthenticated" as const,
  isBootstrapping: false,
  error: null,
  login: async () => false,
  register: async () => false,
  logout: async () => undefined,
  logoutGlobal: async () => undefined,
  resendVerification: async () => true,
  verifyEmail: async () => true,
});

// ── studio-state override (pure, no .ts import chain) ───────────
// The moved page imports `../studio-state`; the test harness's
// customRequire resolves relative to THIS test file and uses CJS
// `require()` (cannot load .ts). We hand the page a minimal but real
// reducer: ADD_MESSAGE appends, SET_GENERATION_STATE stores, and
// every other action returns state unchanged. This is enough for the
// page to render its effects without a deep .ts import chain. The
// assertion (tree contains the Studio shell markers) does not depend
// on reducer correctness — only that the page mounts.
const studioStateOverride = {
  studioReducer: (
    state: Record<string, unknown>,
    action: { type: string; message?: unknown; state?: unknown },
  ) => {
    if (action.type === "ADD_MESSAGE") {
      const history = (state.sessionHistory as unknown[]) ?? [];
      return { ...state, sessionHistory: [...history, action.message] };
    }
    if (action.type === "SET_GENERATION_STATE") {
      return { ...state, generationState: action.state };
    }
    return state;
  },
  initialStudioState: {
    selectedWorkflow: "flux2_txt2img",
    currentJob: null,
    generationState: "idle",
    sessionHistory: [],
    error: null,
    referenceFaceUrl: null,
    editingReferenceBase64: null,
    sessionAssets: [],
    selectedAssetIds: [],
    useTurbo: false,
  },
};

// Stable shell markers that must all render for the /studio route smoke test.
// This proves the route composes the expected shell pieces in Node, while
// deeper browser/runtime behavior remains covered by the broader suite.
const SHELL_MARKERS = ["ChatPanel", "StudioTopBar", "StudioCanvas", "AssetsDrawer"] as const;

void describe("Studio route at /studio", () => {
  void it("renders the full Studio shell (all four shell components present)", async () => {
    const mod = loadComponent("src/app/studio/page.tsx", {
      "@/features/chat/presentation/components/ChatPanel": { ChatPanel: ChatPanelMock },
      "@/features/studio/presentation/components/StudioTopBar": { StudioTopBar: StudioTopBarMock },
      "@/features/studio/presentation/components/StudioCanvas": { StudioCanvas: StudioCanvasMock },
      "@/features/assets/presentation/components/AssetsDrawer": { AssetsDrawer: AssetsDrawerMock },
      "@/features/chat/application": {
        useGenerationJob: useGenerationJobMock,
        submitOrchestrateRequest: () => ({
          outcome: "error",
          stages: [],
        }),
        jobEventsToChatMessages: () => [],
      },
      "@/features/auth/application/use-auth": { useAuth: useAuthMock },
      "../studio-state": studioStateOverride,
      "@/shared/infrastructure/api-client": { submitOrchestrate: async () => ({ outcome: "error" }) },
      "@/features/assets/infrastructure/api": { createProject: async () => ({ id: "p1" }) },
      "@/features/assets/application/use-upload.ts": { executeUpload: async () => ({ r2Url: "", serverAssetId: "a1" }) },
      "@/features/chat/presentation/components/orchestration-ui": { getSafeOrchestrationMessage: () => "" },
      "../../features/chat/domain/dto": {
        createOrchestrateStages: () => [],
      },
    });
    const StudioPage = mod.default as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(StudioPage, null));
    });

    // A single-marker assertion would pass even if most of the shell failed to
    // mount, so the smoke test requires every stable shell marker.
    const present = SHELL_MARKERS.filter((m) =>
      renderer.root.findAllByProps({ "data-mock": m }).length > 0,
    );
    const missing = SHELL_MARKERS.filter((m) => !present.includes(m));
    assert.strictEqual(
      present.length,
      SHELL_MARKERS.length,
      `Studio shell MUST render all ${SHELL_MARKERS.length} shell components; ` +
        `missing: ${missing.join(", ") || "none"}; present: ${present.join(", ")}`,
    );
  });
});
