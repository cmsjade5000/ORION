import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  root: path.resolve("apps/extensions/telegram/orion-miniapp"),
  publicDir: false,
  build: {
    target: "es2018",
    outDir: path.resolve("apps/extensions/telegram/orion-miniapp/public"),
    emptyOutDir: true,
    sourcemap: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: path.resolve("apps/extensions/telegram/orion-miniapp/index.html"),
      output: {
        inlineDynamicImports: true,
        entryFileNames: "app.js",
        chunkFileNames: "app.js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === "style.css") {
            return "styles.css";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
  },
});
