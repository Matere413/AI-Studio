import "@testing-library/jest-dom/vitest";
import React from "react";
import { vi } from "vitest";

vi.mock("next/image", () => ({
  __esModule: true,
  default: function MockImage(props: Record<string, unknown>) {
    return React.createElement("img", {
      alt: props.alt as string,
      src: props.src as string,
      "data-fill": props.fill ? "true" : "false",
    });
  },
}));

// Mock next/font/google — returns a stub with className and variable
vi.mock("next/font/google", () => ({
  Geist: () => ({ className: "mock-geist", variable: "--font-geist-sans" }),
  Geist_Mono: () => ({
    className: "mock-geist-mono",
    variable: "--font-geist-mono",
  }),
}));
