// ─── Component-Level Regression: ChatPanel submit data flow ─────
// Uses react-test-renderer to render the ChatPanel wrapper that
// HomePage must use. Proves that pressing send passes the current
// sessionAssets + selectedAssetIds through to the onSubmit callback.
//
// Layout: renders ChatPanel → mock ChatSidebar → real ChatComposer
//
// ChatSidebar is mocked because its only job is to forward props to
// ChatComposer. The real ChatComposer handles submit interaction
// (typing + clicking send), proving the entire data-flow chain from
// props → onSend → onSubmit works at component level.
//
// If someone removes the selectedAssets mapping or breaks the
// onSend wiring in ChatPanel, this test FAILS.

import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

const require = createRequire(import.meta.url);

// ── Shared presentation mocks ──────────────────────────────────
const sharedPresentationMock = {
  AttachIcon: () => React.createElement("svg", { "aria-hidden": true }),
  SendIcon: () => React.createElement("svg", { "aria-hidden": true }),
  IconButton: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) =>
    React.createElement("button", props, children),
  PillSelect: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) =>
    React.createElement("select", props, children),
  AvatarMark: () => React.createElement("span", { "aria-hidden": true }),
  SettingsIcon: () => React.createElement("svg", { "aria-hidden": true }),
};

// ── Transpile helper ───────────────────────────────────────────
function transpileModule(filePath: string) {
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

// ── Load real ChatComposer ─────────────────────────────────────
const chatComposerJs = transpileModule(
  join(process.cwd(), "src/features/chat/presentation/components/ChatComposer.tsx"),
);
const composerOverrides: Record<string, unknown> = {
  "@/shared/presentation": sharedPresentationMock,
  "./orchestration-ui": require(join(process.cwd(), "src/features/chat/presentation/components/orchestration-ui.ts")),
};
const chatComposerExports = loadModule(chatComposerJs, composerOverrides).exports;
const RealChatComposer = chatComposerExports.ChatComposer as React.ComponentType<Record<string, unknown>>;

// ── Mock ChatSidebar — renders real ChatComposer with same props ─
// This is a pass-through mock. The ONLY thing ChatSidebar does is
// forward submitState, manualControls, selectedAssets, and orchestrationState
// to ChatComposer. The mock preserves this behavior.
function MockChatSidebar(props: Record<string, unknown>) {
  return React.createElement(
    "aside",
    { "data-testid": "mock-chat-sidebar" },
    React.createElement(RealChatComposer, {
      submitState: (props as Record<string, unknown>).submitState as Record<string, unknown>,
      manualControls: (props as Record<string, unknown>).manualControls as Record<string, unknown>,
      selectedAssets: (props as Record<string, unknown>).selectedAssets as Record<string, unknown>,
      orchestrationState: (props as Record<string, unknown>).orchestrationState as Record<string, unknown>,
    }),
  );
}

// ── Load ChatPanel (the component under test) ──────────────────
async function loadChatPanel() {
  const chatPanelJs = transpileModule(
    join(process.cwd(), "src/features/chat/presentation/components/ChatPanel.tsx"),
  );
  const panelExports = loadModule(chatPanelJs, {
    "./ChatSidebar": { ChatSidebar: MockChatSidebar },
  }).exports;
  return panelExports.ChatPanel as React.ComponentType<Record<string, unknown>>;
}

// ── Test helpers ───────────────────────────────────────────────
interface SessionAsset {
  id: string;
  name: string;
  type: string;
  uploadStatus: string;
}

function baseProps(overrides: Record<string, unknown> = {}) {
  const sessionAssets: SessionAsset[] = [
    { id: "a1", name: "Product Photo", type: "image", uploadStatus: "done" },
    { id: "a2", name: "Background", type: "image", uploadStatus: "done" },
    { id: "a3", name: "Uploading asset", type: "image", uploadStatus: "uploading" },
  ];

  return {
    messages: [],
    onSubmit: async (_prompt: string, _assets: SessionAsset[], _ids: string[]) => true,
    disabled: false,
    manualControls: {
      workflow: "flux2_txt2img",
      onWorkflowChange: () => undefined,
      referenceFaceUrl: null,
      onReferenceFaceUrlChange: () => undefined,
      editingReferenceFile: null,
      onEditingReferenceFileChange: () => undefined,
      useTurbo: false,
      onTurboChange: () => undefined,
    },
    sessionAssets,
    selectedAssetIds: ["a1", "a2"],
    orchestrationStages: [],
    ...overrides,
  };
}

// ── Tests ──────────────────────────────────────────────────────
void describe("ChatPanel submit data flow — component-level regression", () => {
  void it("renders selected asset pills from sessionAssets and selectedAssetIds", async () => {
    const ChatPanel = await loadChatPanel();
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatPanel, baseProps()));
    });

    const root = renderer.root;

    // Assert asset pills are rendered — this proves the selectedAssets
    // mapping (filter by selectedAssetIds + map to display format) works.
    const pills = root.findAll(
      (node) => typeof node.type === "string"
        && node.children
        && node.children.some(
          (c) => typeof c === "string" && c.includes("Product Photo"),
        ),
    );
    assert.ok(pills.length > 0, "MUST render pill for 'Product Photo' (id=a1)");

    // "Uploading asset" (a3) should NOT appear because it's NOT in selectedAssetIds
    const hiddenPill = root.findAll(
      (node) => typeof node.type === "string"
        && node.children
        && node.children.some(
          (c) => typeof c === "string" && c.includes("Uploading asset"),
        ),
    );
    assert.strictEqual(hiddenPill.length, 0,
      "MUST NOT render pill for asset not in selectedAssetIds");
  });

  void it("passes current sessionAssets and selectedAssetIds through to onSubmit when send is clicked", async () => {
    const ChatPanel = await loadChatPanel();
    const capturedArgs: unknown[] = [];
    const mockOnSubmit = async (prompt: string, assets: unknown[], ids: string[]) => {
      capturedArgs.push(prompt, assets, ids);
      return true;
    };

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatPanel, baseProps({
        onSubmit: mockOnSubmit,
      })));
    });

    const root = renderer.root;

    // Type a prompt in the ChatComposer textarea
    const textarea = root.findByProps({ "aria-label": "Message Agent" });
    await act(async () =>
      textarea.props.onChange({ target: { value: "Generate a product hero" } }),
    );

    // Click the send button
    const sendButton = root.findByProps({ "aria-label": "Send Message" });
    await act(async () => sendButton.props.onClick());

    // Assert onSubmit was called with (prompt, sessionAssets, selectedAssetIds)
    assert.strictEqual(capturedArgs.length, 3,
      "onSubmit MUST be called with (prompt, sessionAssets, selectedAssetIds)");
    assert.strictEqual(capturedArgs[0], "Generate a product hero");

    // Verify sessionAssets were passed through
    const passedAssets = capturedArgs[1] as Array<{ id: string }>;
    assert.ok(passedAssets, "sessionAssets MUST be passed to onSubmit");
    assert.strictEqual(passedAssets.length, 3);
    assert.strictEqual(passedAssets[0].id, "a1");
    assert.strictEqual(passedAssets[1].id, "a2");
    assert.strictEqual(passedAssets[2].id, "a3");

    // Verify selectedAssetIds were passed through
    const passedIds = capturedArgs[2] as string[];
    assert.ok(passedIds, "selectedAssetIds MUST be passed to onSubmit");
    assert.strictEqual(passedIds.length, 2);
    assert.strictEqual(passedIds[0], "a1");
    assert.strictEqual(passedIds[1], "a2");
  });

  void it("omits non-selected assets from UI and passes empty selectedAssetIds when none selected", async () => {
    const ChatPanel = await loadChatPanel();
    const capturedArgs: unknown[] = [];
    const mockOnSubmit = async (_prompt: string, _assets: unknown[], ids: string[]) => {
      capturedArgs.push(ids);
      return true;
    };

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatPanel, baseProps({
        onSubmit: mockOnSubmit,
        selectedAssetIds: [],
      })));
    });

    const root = renderer.root;

    // Assert no asset pills are rendered
    const pills = root.findAll(
      (node) => typeof node.type === "string"
        && node.children
        && node.children.some(
          (c) => typeof c === "string" && c.includes("·"),
        ),
    );
    assert.strictEqual(pills.length, 0,
      "MUST NOT render asset pills when selectedAssetIds is empty");

    // Type and send
    const textarea = root.findByProps({ "aria-label": "Message Agent" });
    await act(async () =>
      textarea.props.onChange({ target: { value: "Test with no assets" } }),
    );
    const sendButton = root.findByProps({ "aria-label": "Send Message" });
    await act(async () => sendButton.props.onClick());

    // Assert onSubmit was called with empty selectedAssetIds
    assert.deepStrictEqual(capturedArgs[0], [],
      "MUST pass empty array when no assets selected");
  });

  void it("uses updated sessionAssets and selectedAssetIds when props change before submit — regression guard", async () => {
    const ChatPanel = await loadChatPanel();
    const capturedArgs: unknown[] = [];
    const mockOnSubmit = async (prompt: string, assets: unknown[], ids: string[]) => {
      capturedArgs.push(prompt, assets, ids);
      return true;
    };

    // Initial: 3 session assets, 2 selected (a1, a2)
    const initialAssets: SessionAsset[] = [
      { id: "a1", name: "Product Photo", type: "image", uploadStatus: "done" },
      { id: "a2", name: "Background", type: "image", uploadStatus: "done" },
      { id: "a3", name: "Uploading asset", type: "image", uploadStatus: "uploading" },
    ];

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatPanel, baseProps({
        onSubmit: mockOnSubmit,
        sessionAssets: initialAssets,
        selectedAssetIds: ["a1", "a2"],
      })));
    });

    // Rerender with DIFFERENT session assets and selectedAssetIds
    const updatedAssets: SessionAsset[] = [
      { id: "a4", name: "New Background", type: "image", uploadStatus: "done" },
      { id: "a5", name: "Style Guide", type: "file", uploadStatus: "done" },
      { id: "a6", name: "Logo", type: "image", uploadStatus: "done" },
    ];
    await act(async () => {
      renderer.update(React.createElement(ChatPanel, baseProps({
        onSubmit: mockOnSubmit,
        sessionAssets: updatedAssets,
        selectedAssetIds: ["a4", "a5"],
      })));
    });

    const root = renderer.root;

    // Type and submit AFTER the rerender
    const textarea = root.findByProps({ "aria-label": "Message Agent" });
    await act(async () =>
      textarea.props.onChange({ target: { value: "Generate with updated assets" } }),
    );
    const sendButton = root.findByProps({ "aria-label": "Send Message" });
    await act(async () => sendButton.props.onClick());

    // Assert onSubmit was called with the UPDATED values, NOT first-render values
    assert.strictEqual(capturedArgs.length, 3,
      "onSubmit MUST be called with (prompt, sessionAssets, selectedAssetIds)");
    assert.strictEqual(capturedArgs[0], "Generate with updated assets");

    const passedAssets = capturedArgs[1] as Array<{ id: string }>;
    assert.strictEqual(passedAssets.length, 3,
      "MUST pass updated sessionAssets (3 items) after rerender");
    assert.strictEqual(passedAssets[0].id, "a4",
      "MUST be a4 (updated), NOT a1 (first-render value)");
    assert.strictEqual(passedAssets[1].id, "a5",
      "MUST be a5 (updated), NOT a2 (first-render value)");
    assert.strictEqual(passedAssets[2].id, "a6",
      "MUST be a6 (updated), NOT a3 (first-render value)");

    const passedIds = capturedArgs[2] as string[];
    assert.strictEqual(passedIds.length, 2,
      "MUST pass updated selectedAssetIds (2 items) after rerender");
    assert.strictEqual(passedIds[0], "a4",
      "MUST be a4, NOT a1 from first render");
    assert.strictEqual(passedIds[1], "a5",
      "MUST be a5, NOT a2 from first render");

    // Also verify: a1/a2/a3 are NOT in the submitted values
    const allSubmittedAssetIds = passedAssets.map((a) => a.id);
    assert.ok(!allSubmittedAssetIds.includes("a1"),
      "MUST NOT include first-render asset a1");
    assert.ok(!allSubmittedAssetIds.includes("a2"),
      "MUST NOT include first-render asset a2");
    assert.strictEqual(passedIds.includes("a1"), false,
      "MUST NOT include first-render selectedAssetId a1");
    assert.strictEqual(passedIds.includes("a2"), false,
      "MUST NOT include first-render selectedAssetId a2");
  });
});
