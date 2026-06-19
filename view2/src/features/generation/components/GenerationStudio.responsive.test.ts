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

  it("lays out the studio shell as a desktop grid with a 1024px collapse breakpoint", () => {
    const css = readFileSync(join(componentsDir, "GenerationStudio.module.css"), "utf8");

    expect(css).toContain("grid-template-columns: 320px 1fr 320px");
    expect(css).toContain("var(--topbar-height) 1fr");
    expect(css).toContain("@media (max-width: 1023px)");
  });

  it("uses the mobile overlay breakpoint for the assets drawer", () => {
    const css = readFileSync(join(componentsDir, "AssetsDrawer.module.css"), "utf8");

    expect(css).toContain("@media (max-width: 1023px)");
    expect(css).toContain("position: fixed");
  });
});
