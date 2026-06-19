import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

const rootDir = fileURLToPath(new URL(".", import.meta.url));
const apiBaseUrl =
  process.env.GENERATION_API_BASE_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  turbopack: {
    root: rootDir,
  },
  async rewrites() {
    return [
      {
        source: "/api/generate",
        destination: `${apiBaseUrl}/generate`,
      },
      {
        source: "/api/ws/generate/:jobId",
        destination: `${apiBaseUrl}/ws/generate/:jobId`,
      },
      {
        source: "/api/images/:jobId",
        destination: `${apiBaseUrl}/images/:jobId`,
      },
    ];
  },
};

export default nextConfig;
