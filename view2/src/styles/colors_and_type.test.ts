import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function resolveToken(source: string, name: string): string {
  const tokenMatch = source.match(new RegExp(`--${name}:\\s*([^;]+);`));

  if (!tokenMatch) {
    throw new Error(`Missing CSS token --${name}`);
  }

  const value = tokenMatch[1].trim();

  if (value.startsWith("var(")) {
    const nestedMatch = value.match(/--([^)]+)/);

    if (!nestedMatch) {
      throw new Error(`Unsupported token reference for --${name}`);
    }

    return resolveToken(source, nestedMatch[1]);
  }

  return value;
}

function channel(hex: string, offset: number): number {
  return Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
}

function relativeLuminance(hex: string): number {
  const components = [1, 3, 5].map((offset) => channel(hex, offset)).map((value) => {
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * components[0] + 0.7152 * components[1] + 0.0722 * components[2];
}

function contrastRatio(foreground: string, background: string): number {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background));

  return (lighter + 0.05) / (darker + 0.05);
}

describe("colors_and_type.css", () => {
  it("does not reference missing custom font assets", () => {
    const source = readFileSync(join(process.cwd(), "src/styles/colors_and_type.css"), "utf8");

    expect(source).not.toMatch(/@font-face/);
    expect(source).not.toMatch(/\/fonts\//);
    expect(source).toContain("--font-mono:    ui-monospace");
    expect(source).toContain("--font-display: ui-sans-serif");
  });

  it("keeps the core text tokens above the required contrast thresholds", () => {
    const source = readFileSync(join(process.cwd(), "src/styles/colors_and_type.css"), "utf8");
    const background = resolveToken(source, "bg-0");
    const primaryText = resolveToken(source, "fg-1");
    const mutedText = resolveToken(source, "fg-3");

    expect(contrastRatio(primaryText, background)).toBeGreaterThanOrEqual(12);
    expect(contrastRatio(mutedText, background)).toBeGreaterThanOrEqual(4.5);
  });
});
