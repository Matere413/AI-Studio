import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useMediaQuery } from "./useMediaQuery";

function createMatchMedia(width: number) {
  return vi.fn().mockImplementation((query: string) => {
    const breakpoint = Number(query.match(/min-width:\s*(\d+)px/)?.[1] ?? 0);
    const matches = width >= breakpoint;

    return {
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    };
  });
}

describe("useMediaQuery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    [1023, false],
    [1024, true],
  ])("returns %s at the 1024px boundary", (width, expected) => {
    vi.stubGlobal("matchMedia", createMatchMedia(width as number));

    const { result } = renderHook(() => useMediaQuery(1024));

    expect(result.current).toBe(expected);
  });
});
