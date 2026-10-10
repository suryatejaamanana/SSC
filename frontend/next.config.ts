import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Backend allows 20MB PDF uploads; the proxy default would cut them at 10MB.
  experimental: { proxyClientMaxBodySize: "25mb" },
  // Single-service deploy: FastAPI runs inside the same container and the
  // browser only ever talks to this origin.
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
  // Pin the workspace root so Turbopack doesn't walk up to an unrelated
  // package-lock.json in the home directory.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
