import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("GenerationStudio visual polish", () => {
  it("declares visible focus styles for interactive controls", () => {
    const source = readFileSync(
      join(process.cwd(), "src/features/generation/components/GenerationStudio.module.css"),
      "utf8"
    );

    expect(source).toContain(".pill:focus-visible");
    expect(source).toContain(".iconButton:focus-visible");
    expect(source).toContain(".drawerRemove:focus-visible");
    expect(source).toContain(".topAppBarAction:focus-visible");
    expect(source).toContain(".promptField:focus-visible");
    expect(source).toContain(".uploadField input:focus-visible");
    expect(source).toContain("outline: 2px solid var(--wheat-400)");
    expect(source).toContain("outline-offset: 2px");
  });

  it("connects reduced-motion suppression to the rendered shell and pulsing status tone", () => {
    const componentSource = readFileSync(
      join(process.cwd(), "src/features/generation/components/GenerationStudio.tsx"),
      "utf8"
    );
    const source = readFileSync(
      join(process.cwd(), "src/features/generation/components/GenerationStudio.module.css"),
      "utf8"
    );

    expect(componentSource).toContain("className={styles.shell}");
    expect(source).toContain("@media (prefers-reduced-motion: reduce)");
    expect(source).toContain(".shell,");
    expect(source).toContain(".statusTone[data-pulsing=\"true\"]");
    expect(source).toContain("animation: none !important");
    expect(source).toContain("transition: none !important");
  });
});
