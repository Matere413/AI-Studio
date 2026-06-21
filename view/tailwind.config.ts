import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#1c1917",
        surface: {
          DEFAULT: "#292524",
          hover: "#44403c",
        },
        border: "#2e2820",
        primary: "#F5F5F5",
        muted: "#8F8F8F",
        accent: "#d97706",
        highlight: "#eab208",
        error: "#F28B82",
        success: "#81C995",
      },
      fontFamily: {
        display: [
          "system-ui",
          "-apple-system",
          "Helvetica Neue",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        body: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "2xl": ["24px", { lineHeight: "1.2" }],
        xl: ["20px", { lineHeight: "1.2" }],
        lg: ["16px", { lineHeight: "1.2" }],
        base: ["14px", { lineHeight: "1.5" }],
        sm: ["13px", { lineHeight: "1.5" }],
        xs: ["11px", { lineHeight: "1.4" }],
      },
      spacing: {
        18: "4.5rem",
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
      },
      transitionTimingFunction: {
        studio: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      transitionDuration: {
        studio: "150ms",
      },
      letterSpacing: {
        ui: "0.02em",
        caps: "0.06em",
      },
    },
  },
  plugins: [],
};

export default config;
