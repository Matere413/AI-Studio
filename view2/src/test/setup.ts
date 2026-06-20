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
