import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const componentsDir = join(__dirname);

describe("GenerationStudio responsive styles", () => {
  it("narrows the chat sidebar below 1280px", () => {
    const css = readFileSync(join(componentsDir, "ChatSidebar.module.css"), "utf8");

    expect(css).toContain("@media (max-width: 1279px)");
    expect(css).toContain("flex-basis: 280px");
  });

  it("auto-collapses the assets drawer below 1280px", () => {
    const css = readFileSync(join(componentsDir, "AssetsDrawer.module.css"), "utf8");

    expect(css).toContain("@media (max-width: 1279px)");
    expect(css).toContain("display: none");
  });
});
