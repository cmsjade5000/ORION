import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: [
      "src/plugins/**/*.test.ts",
      "src/plugins/**/__tests__/*.test.ts",
      "apps/extensions/**/*.test.ts",
      "apps/extensions/**/__tests__/*.test.ts",
      "app/src/**/*.test.ts",
      "db/src/**/*.test.ts",
    ],
  },
});
