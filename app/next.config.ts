import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    externalDir: true
  },
  serverExternalPackages: ["better-sqlite3"],
  outputFileTracingRoot: path.join(__dirname, ".."),
  webpack: (config, { isServer }) => {
    if (isServer) {
      config.externals = config.externals ?? [];
      config.externals.push({
        "better-sqlite3": "commonjs better-sqlite3"
      });
    }

    return config;
  }
};

export default nextConfig;
