import { describe, it } from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import TestRenderer, { act } from "react-test-renderer";

import * as orchestrationUi from "../components/orchestration-ui.ts";

const require = createRequire(import.meta.url);

async function loadChatComposer() {
  const file = join(process.cwd(), "src/features/chat/presentation/components/ChatComposer.tsx");
  const source = readFileSync(file, "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
  }).outputText;
  const cjsModule = { exports: {} as Record<string, unknown> };
  const localRequire = (id: string) => {
    if (id === "react") return React;
    if (id === "react/jsx-runtime") return require("react/jsx-runtime");
    if (id === "./orchestration-ui") return orchestrationUi;
    if (id === "@/shared/presentation") {
      return {
        AttachIcon: () => React.createElement("svg", { "aria-hidden": true }),
        SendIcon: () => React.createElement("svg", { "aria-hidden": true }),
        IconButton: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => React.createElement("button", props, children),
        PillSelect: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => React.createElement("select", props, children),
      };
    }
    return require(id);
  };
  new Function("require", "module", "exports", js)(localRequire, cjsModule, cjsModule.exports);
  return cjsModule.exports.ChatComposer as React.ComponentType<Record<string, unknown>>;
}

function baseProps(overrides: Record<string, unknown> = {}) {
  return {
    submitState: { onSend: () => true, disabled: false },
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
    selectedAssets: { assets: [] },
    orchestrationState: { stages: [] },
    ...overrides,
  };
}

void describe("ChatComposer rendered orchestration UI", () => {
  void it("renders Chat and Manual tabs, hides manual controls until Manual is selected, and shows selected assets", async () => {
    const ChatComposer = await loadChatComposer();
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatComposer, baseProps({
        selectedAssets: { assets: [{ id: "asset-1", name: "Hero.png", uploadStatus: "done" }] },
      })));
    });

    const root = renderer.root;
    assert.ok(root.findAllByProps({ role: "tab" }).some((node) => node.children.includes("Chat")));
    assert.ok(root.findAllByProps({ role: "tab" }).some((node) => node.children.includes("Manual")));
    assert.strictEqual(root.findAllByProps({ "aria-label": "Workflow" }).length, 0);
    assert.ok(root.findAll((node) => node.type === "span" && node.children.join("").includes("Hero.png · done")).length > 0);

    await act(async () => {
      root.findAllByProps({ role: "tab" }).find((node) => node.children.includes("Manual"))!.props.onClick();
    });

    assert.ok(root.findAllByProps({ "aria-label": "Workflow" }).length >= 1);
  });

  void it("keeps the typed prompt when orchestration submission reports failure", async () => {
    const ChatComposer = await loadChatComposer();
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(ChatComposer, baseProps({ submitState: { onSend: async () => false } })));
    });
    const textarea = renderer.root.findByProps({ "aria-label": "Message Agent" });

    await act(async () => textarea.props.onChange({ target: { value: "Retry this prompt" } }));
    await act(async () => renderer.root.findByProps({ "aria-label": "Send Message" }).props.onClick());

    assert.strictEqual(renderer.root.findByProps({ "aria-label": "Message Agent" }).props.value, "Retry this prompt");
  });
});
