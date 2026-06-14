import { describe, it, expect } from "vitest";
import { truncatePrompt, MAX_PROMPT_LENGTH } from "./ImageGallery";

describe("truncatePrompt (Spec: Session History Gallery — Scenario: Populated gallery)", () => {
  it("returns prompt unchanged if under max length", () => {
    expect(truncatePrompt("A fiery sunset")).toBe("A fiery sunset");
  });

  it("returns prompt unchanged if exactly at max length", () => {
    const promptAtMax = "x".repeat(MAX_PROMPT_LENGTH);
    expect(truncatePrompt(promptAtMax)).toBe(promptAtMax);
  });

  it("truncates and appends ellipsis when over max length", () => {
    const promptOverMax = "x".repeat(MAX_PROMPT_LENGTH + 20);
    const result = truncatePrompt(promptOverMax);
    expect(result).toBe("x".repeat(MAX_PROMPT_LENGTH) + "...");
  });

  it("truncates at exactly MAX_PROMPT_LENGTH characters before ellipsis", () => {
    const prompt200 = "a".repeat(200);
    const result = truncatePrompt(prompt200);
    expect(result.length).toBe(MAX_PROMPT_LENGTH + 3);
  });

  it("handles empty string", () => {
    expect(truncatePrompt("")).toBe("");
  });
});