// ─── Unit Tests: Landing copy + LandingPage render ───────────────
// Asserts the marketing-landing contract (spec: marketing-landing):
//   - All visible strings equal values from `landing-copy.ts`
//   - Primary CTA href === "/studio", label === "Start a visual session"
//   - Secondary CTA href === "/register", label === "Shape your next image"
//   - No `bg-gradient-*` classes (DESIGN.md bans gradients)
//   - Mono + display tokens present (technical-instrument aesthetic)
// Uses the same transpile + react-test-renderer harness as
// verify-page.test.ts / auth-forms.test.ts (bare Node, no DOM).

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

// Collect every rendered className string so we can assert no gradients.
function collectClassNames(node: TestRenderer.ReactTestInstance, acc: string[] = []): string[] {
  const className = node.props?.className;
  if (typeof className === "string" && className.length > 0) {
    acc.push(...className.split(/\s+/));
  }
  for (const child of node.children ?? []) {
    if (typeof child === "object" && child !== null) {
      collectClassNames(child as TestRenderer.ReactTestInstance, acc);
    }
  }
  return acc;
}

// Walk the tree and collect all text content.
function collectText(node: TestRenderer.ReactTestInstance, acc: string[] = []): string[] {
  const children = node.children ?? [];
  for (const child of children) {
    if (typeof child === "string") {
      acc.push(child);
    } else if (typeof child === "number") {
      acc.push(String(child));
    } else if (typeof child === "object" && child !== null) {
      collectText(child as TestRenderer.ReactTestInstance, acc);
    }
  }
  return acc;
}

// next/link mock: render an <a> with the given href so href + children are assertable.
// Prop-preserving form: destructure href + children, spread ...props onto <a> so
// externally visible attributes (className, data-state, aria-*, etc.) survive the
// mock and can be asserted via findAllByProps. The bare ({ href, children }) form
// silently drops every other prop, making contract assertions pass vacuously.
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

void describe("LandingPage", () => {
  void it("renders visible strings sourced from landing-copy.ts", async () => {
    const { landingCopy } = await import("../data/landing-copy.ts");
    const mod = loadComponent("src/features/landing/presentation/components/LandingPage.tsx", {
      "next/link": LinkMock,
      "./Hero": loadComponent("src/features/landing/presentation/components/Hero.tsx", {
        "next/link": LinkMock,
      }),
      "./InstrumentReadout": loadComponent("src/features/landing/presentation/components/InstrumentReadout.tsx"),
      "../data/landing-copy": { landingCopy },
    });
    const LandingPage = mod.LandingPage as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LandingPage, null));
    });

    const text = collectText(renderer.root).join(" ");

    // Hero strings from the data file MUST appear in the DOM.
    assert.ok(text.includes(landingCopy.hero.headline), "MUST render hero.headline");
    assert.ok(text.includes(landingCopy.hero.subhead), "MUST render hero.subhead");
    assert.ok(text.includes(landingCopy.hero.eyebrow), "MUST render hero.eyebrow");
    assert.ok(
      text.includes(landingCopy.hero.primaryCta.label),
      "MUST render primary CTA label",
    );
    assert.ok(
      text.includes(landingCopy.hero.secondaryCta.label),
      "MUST render secondary CTA label",
    );
    // Readout strings from the data file MUST appear.
    assert.ok(text.includes(landingCopy.readout.eyebrow), "MUST render readout.eyebrow");
    for (const line of landingCopy.readout.lines) {
      assert.ok(text.includes(line), `MUST render readout line: ${line}`);
    }
  });

  void it("primary CTA links to /studio, secondary CTA links to /register", async () => {
    const { landingCopy } = await import("../data/landing-copy.ts");
    const mod = loadComponent("src/features/landing/presentation/components/LandingPage.tsx", {
      "next/link": LinkMock,
      "./Hero": loadComponent("src/features/landing/presentation/components/Hero.tsx", {
        "next/link": LinkMock,
      }),
      "./InstrumentReadout": loadComponent("src/features/landing/presentation/components/InstrumentReadout.tsx"),
      "../data/landing-copy": { landingCopy },
    });
    const LandingPage = mod.LandingPage as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LandingPage, null));
    });

    const anchors = renderer.root.findAllByType("a");
    const hrefs = anchors.map((a) => a.props.href);
    assert.ok(hrefs.includes("/studio"), `MUST include a link to /studio; got: ${hrefs.join(", ")}`);
    assert.ok(hrefs.includes("/register"), `MUST include a link to /register; got: ${hrefs.join(", ")}`);

    // The primary CTA label must be on the /studio anchor, secondary on /register.
    const studioAnchor = anchors.find((a) => a.props.href === "/studio");
    const registerAnchor = anchors.find((a) => a.props.href === "/register");
    assert.ok(studioAnchor, "studio CTA anchor MUST exist");
    assert.ok(registerAnchor, "register CTA anchor MUST exist");
    const studioText = collectText(studioAnchor!).join(" ");
    const registerText = collectText(registerAnchor!).join(" ");
    assert.ok(
      studioText.includes(landingCopy.hero.primaryCta.label),
      "studio anchor MUST carry the primary CTA label",
    );
    assert.ok(
      registerText.includes(landingCopy.hero.secondaryCta.label),
      "register anchor MUST carry the secondary CTA label",
    );
  });

  void it("uses no gradient classes and applies mono + display tokens", async () => {
    const { landingCopy } = await import("../data/landing-copy.ts");
    const mod = loadComponent("src/features/landing/presentation/components/LandingPage.tsx", {
      "next/link": LinkMock,
      "./Hero": loadComponent("src/features/landing/presentation/components/Hero.tsx", {
        "next/link": LinkMock,
      }),
      "./InstrumentReadout": loadComponent("src/features/landing/presentation/components/InstrumentReadout.tsx"),
      "../data/landing-copy": { landingCopy },
    });
    const LandingPage = mod.LandingPage as React.ComponentType;

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LandingPage, null));
    });

    const classes = collectClassNames(renderer.root);
    const gradientClasses = classes.filter((c) => c.includes("gradient"));
    assert.strictEqual(
      gradientClasses.length,
      0,
      `MUST NOT use gradient classes (DESIGN.md ban); found: ${gradientClasses.join(", ")}`,
    );
    assert.ok(
      classes.some((c) => c === "font-mono"),
      "MUST use the font-mono token (technical-instrument aesthetic)",
    );
    assert.ok(
      classes.some((c) => c === "font-display"),
      "MUST use the font-display token (headline typography)",
    );
  });

  // Tertiary Sign-in CTA contract (spec delta: marketing-landing).
  // Asserts the data shape (Sign in → /login), that the /login anchor is
  // rendered carrying the label, and the ghost-button dark-token contract
  // (transparent bg, 1px border, hover surface, 150ms motion, no gradient).
  // Per design Decision 8, the 1280px no-wrap stability is a manual evidence
  // artifact — this test asserts only the contract-level preconditions.
  void it("renders the tertiary Sign-in CTA as a ghost link to /login", async () => {
    const { landingCopy } = await import("../data/landing-copy.ts");
    const mod = loadComponent("src/features/landing/presentation/components/LandingPage.tsx", {
      "next/link": LinkMock,
      "./Hero": loadComponent("src/features/landing/presentation/components/Hero.tsx", {
        "next/link": LinkMock,
      }),
      "./InstrumentReadout": loadComponent("src/features/landing/presentation/components/InstrumentReadout.tsx"),
      "../data/landing-copy": { landingCopy },
    });
    const LandingPage = mod.LandingPage as React.ComponentType;

    // Data contract: tertiaryCta MUST be present on landingCopy.hero with
    // the Sign in label and /login href (spec: "Tertiary Sign-in CTA on the
    // Landing Hero").
    assert.ok(landingCopy.hero.tertiaryCta, "landingCopy.hero.tertiaryCta MUST be defined");
    assert.strictEqual(landingCopy.hero.tertiaryCta!.label, "Sign in");
    assert.strictEqual(landingCopy.hero.tertiaryCta!.href, "/login");

    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(React.createElement(LandingPage, null));
    });

    // The /login anchor MUST be rendered and carry the Sign in label.
    const anchors = renderer.root.findAllByType("a");
    const loginAnchor = anchors.find((a) => a.props.href === "/login");
    assert.ok(loginAnchor, "MUST render an anchor to /login (the tertiary Sign-in CTA)");
    const loginText = collectText(loginAnchor!).join(" ");
    assert.ok(
      loginText.includes("Sign in"),
      "the /login anchor MUST carry the 'Sign in' label",
    );

    // Ghost-button contract (DESIGN.md): transparent bg, 1px border, hover
    // surface, 150ms motion. These are the contract-level preconditions the
    // manual 1280px screenshot review relies on; class presence is the
    // strongest signal react-test-renderer can give without a layout engine.
    const cls = loginAnchor!.props.className as string;
    assert.ok(cls.includes("border"), "Sign-in CTA MUST have a border (ghost button)");
    assert.ok(cls.includes("border-border"), "Sign-in CTA MUST use the border-border token");
    assert.ok(
      cls.includes("bg-transparent"),
      "Sign-in CTA MUST have a transparent background (ghost button)",
    );
    assert.ok(
      cls.includes("duration-studio"),
      "Sign-in CTA MUST use 150ms motion (duration-studio token)",
    );

    // No gradient on the new anchor (DESIGN.md anti-pattern).
    const gradientOnLogin = cls.split(/\s+/).filter((c) => c.includes("gradient"));
    assert.strictEqual(
      gradientOnLogin.length,
      0,
      `Sign-in CTA MUST NOT use gradient classes; found: ${gradientOnLogin.join(", ")}`,
    );
  });
});